from collections import namedtuple
import json
import logging
from threading import RLock
import greenlet
from api.core.data_structures.queues import QueueEx
from api.core.signals.events import EventHandler
from api.core.utility import getUniqueId, Timer
from api.web.web_utility import SignalActions
import gevent
import gevent.event

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class WebSocket(EventHandler):
    """ Base class for all web socket interactions. """
    class OP:
        """ Contains all operation codes, indicating what message is for.
            These codes are passed to the client directly via templating, so
            no need to modify elsewhere. """
        ADD_MARKER = 1
        ADD_LINE = 2
        REMOVE_ITEM = 3

        ADD_ROW = 4
        UPDATE_ROW = 6
        SET_HEADER = 7

        SET_ELEMENT_INNER_HTML = 8
        EXECUTE_JAVASCRIPT = 9

        PING = 0

    def __init__(self, webSocket, onRegisteredFunc=None):
        super(WebSocket, self).__init__(processSignalFunc=self.onUpdate, onRegisteredFunc=onRegisteredFunc)

        assert webSocket is not None

        self.web_socket = webSocket
        self.is_cleaned_up = False
        self.controls = dict()

        self.pingTimer = Timer(4000,False)

        self.cleanup_funcs = []

    def ping(self):
        self.send({'static_op' : WebSocket.OP.PING})

        pingBack = self.receive()

        if pingBack != 'PING_BACK':
            self.cleanup()

    def pingFreqLimited(self):
        if self.pingTimer.ticked():
            self.ping()

    def send(self, data):
        """ Sends a dictionary to the client in json form.
            @param data a dictionary to be sent to the client. """
        dataToSend = json.dumps(data)

        try:
            self.web_socket.send(dataToSend)
        except Exception as e:
            self.cleanup()
            logger.debug('Web socket connection terminated while sending, reason: %s, exception type %s' % (e, type(e)))

    def receive(self):
        try:
            return self.web_socket.receive()
        except Exception as e:
            self.cleanup()
            logger.debug('Web socket connection terminated while receiving, reason: %s, exception type %s' % (e, type(e)))
            return None

    def onUpdate(self, signaler, data):
        if data is None:
            return

        if SignalActions.SOCKET in data:
            data[SignalActions.SOCKET](self.controls, data)

    def cleanup(self):
        self.is_cleaned_up = True

        # Do not unregister from all here, the thread managing the socket does this
        # See WebSocketGroup.processWebSocket. This is important; we want the unregistering
        # to be done from a different thread to the one which the send operation originated from.
        # This avoids a problem where we might be iterating through event signalers, signal an event
        # but then the event signaler collection decreases in size as one is cleaned up. If from a different thread
        # it will change size after we have finished iterating through it.
        for item in self.cleanup_funcs:
            item(self)

    def addControls(self, controls):
        for control in controls:
            self.addControl(control)

    def addControl(self, control):
        assert isinstance(control, Control)
        self.controls[control.control_name] = control
        control.web_socket = self


def addPopupTextToDict(dic, popupText):
    addItemToDict(dic, 'popupText', popupText)


def addPropertiesToDict(dic, properties):
    properties = json.dumps(properties)
    addItemToDict(dic, 'properties', properties)


def addItemToDict(dic, key, item):
    if item is not None:
        dic.update({key: item})


def getHashKey(hashKey):
    if hashKey is None:
        hashKey = getUniqueId()

    return hash(hashKey)


class Control(object):
    """ A control is a dynamic object on a web page, e.g.
        a map or a table which updates in real time.

        Each control has a specific communication protocol with
        the javascript client.

        Multiple controls can exist on a single web page, using
        the same web socket. """

    def __init__(self, controlName):
        super(Control, self).__init__()
        assert isinstance(controlName, basestring)

        self.web_socket = None
        self.control_name = controlName

        # Often we want to load data into a control object so that
        # we can setup callbacks and other useful things on a per
        # connection/per control basis.
        #
        # We might have multiple threads potentially hitting the same
        # critical sections, and we don't want to initialize an item
        # multiple times.
        #
        # Use this lock to protect these critical sections.
        self.control_attribute_creation_lock = RLock()

    def send(self, data):
        # Failure here means control is not properly registered
        # with web socket.
        assert self.web_socket is not None
        assert isinstance(self.web_socket, WebSocket)

        dataToSend = dict()

        dataToSend[self.control_name] = data
        self.web_socket.send(dataToSend)


    def receive(self):
        return self.web_socket.receive()

    def setElementInnerHtml(self, elementId, html):
        data = {'op': WebSocket.OP.SET_ELEMENT_INNER_HTML,
                'elementId': elementId,
                'html': html}

        self.send(data)

    def executeJavascript(self, javascript):
        data = {'op' : WebSocket.OP.EXECUTE_JAVASCRIPT,
                'javascript' : javascript}

        self.send(data)

class DocumentControl(Control):
    def __init__(self, name):
        super(DocumentControl, self).__init__(name)


class MapControl(Control):
    """ Control for interfacing a leaflet map. """

    def __init__(self, controlName):
        super(MapControl, self).__init__(controlName=controlName)

    def addMarker(self, coord, properties=None, popupText=None, hashKey=None):
        """ Adds a marker to the client's map.

            @param coord coord in form [x,y], this is location on map to place marker.
            @param properties properties in dict form (see leaflet API) e.g. 'color' : 'red'
            @param popupText when object is clicked on map this text will appear.
            @param hashKey a key used to hash the line object on client side,
                           if optional one will be assigned. This is needed to delete
                           objects later on.
            @return hash key used. """
        assert coord is not None

        hashKey = getHashKey(hashKey)

        data = {'op': WebSocket.OP.ADD_MARKER,
                'coord': coord,
                'hashKey': hashKey}

        addPropertiesToDict(data, properties)
        addPopupTextToDict(data, popupText)

        self.send(data)
        return hashKey

    def addLine(self, coords, properties=None, popupText=None, hashKey=None):
        """ Adds a line to the client's map.

            @param coords coord list in form [[x,y],[x,y]..], this is location on map to place line.
            @param properties properties in dict form (see leaflet API) e.g. 'color' : 'red'
            @param popupText when object is clicked on map this text will appear.
            @param hashKey a key used to hash the line object on client side,
                           if optional one will be assigned. This is needed to delete
                           objects later on.
            @return hash key used. """
        assert coords is not None

        hashKey = getHashKey(hashKey)

        data = {'op': WebSocket.OP.ADD_LINE,
                'coords': coords,
                'hashKey': hashKey}

        addPropertiesToDict(data, properties)
        addPopupTextToDict(data, popupText)

        self.send(data)
        return hashKey

    def removeItem(self, hashKey):
        assert hashKey is not None

        hashKey = hash(hashKey)

        data = {'op': WebSocket.OP.REMOVE_ITEM,
                'hashKey': hashKey}

        self.send(data)
        return hashKey


class TableControl(Control):
    """ Control for interfacing an html table. """

    def __init__(self, controlName):
        super(TableControl, self).__init__(controlName=controlName)

    @staticmethod
    def getCell(cellContents, width=None, height=None, className=None, header=False):
        ntuple = namedtuple('cell',['cellContents', 'width', 'height', 'className', 'header'])
        return ntuple(cellContents='%s' % cellContents, width=width, height=height, className=className, header=header)

    def addRow(self, hashKey, cells, rowIndex=None):
        assert cells is not None

        hashKey = getHashKey(hashKey)

        data = {'op': WebSocket.OP.ADD_ROW,
                'hashKey': hashKey,
                'cells': cells,
                'rowIndex' : rowIndex}

        self.send(data)
        return hashKey

    def updateRow(self, hashKey, cells, rowIndex=None):
        assert cells is not None

        hashKey = getHashKey(hashKey)

        data = {'op': WebSocket.OP.UPDATE_ROW,
                'hashKey': hashKey,
                'cells': cells,
                'rowIndex': rowIndex}

        self.send(data)
        return hashKey

    def setHeader(self, cells):
        assert cells is not None

        data = {'op': WebSocket.OP.SET_HEADER,
                'cells' : cells}

        self.send(data)

    def removeItem(self, hashKey):
        assert hashKey is not None

        hashKey = hash(hashKey)

        data = {'op': WebSocket.OP.REMOVE_ITEM,
                'hashKey': hashKey}

        self.send(data)
        return hashKey

class DivControl(Control):
    """ Control for interfacing a div. """

    def __init__(self, controlName):
        super(DivControl, self).__init__(controlName=controlName)

    @staticmethod
    def getCell(cellContents, className='span1',wrapIn=['p']):
        if wrapIn is not None:
            for item in wrapIn:
                cellContents = '<%s>%s</%s>' % (item, cellContents, item)

        ntuple = namedtuple('cell',['cellContents', 'className'])
        return ntuple(cellContents='%s' % cellContents, className=className)

    @staticmethod
    def getContainerHtml(contents, className=None, id=None):
        assert isinstance(contents, basestring)

        if className is not None:
            classHtml = ' class = "%s"' % className
        else:
            classHtml = ''

        if id is not None:
            idHtml = ' id = "%s"' % id
        else:
            idHtml = ''

        return '<div%s%s>%s</div>' % (classHtml,idHtml,contents)

    @staticmethod
    def getCellHtml(cellContents, className='span1', wrapIn=['p'], id=None):
        result = DivControl.getCell(cellContents, className, wrapIn)
        cellHtml = result.cellContents
        cellClass = result.className
        return DivControl.getContainerHtml(cellHtml, cellClass, id)

    @staticmethod
    def getRowHtml(cellsHtml, rowClass='row-fluid', id=None):
        cellsHtml = ''.join(cellsHtml)
        return DivControl.getContainerHtml(cellsHtml, rowClass,id)

    def addRow(self, hashKey, cells, rowIndex=None, rowClass='row-fluid'):
        assert cells is not None

        hashKey = getHashKey(hashKey)

        data = {'op': WebSocket.OP.ADD_ROW,
                'hashKey': hashKey,
                'cells': cells,
                'rowIndex' : rowIndex,
                'rowClass' : rowClass}

        self.send(data)
        return hashKey

    def updateRow(self, hashKey, cells, rowIndex=None, rowClass='row-fluid'):
        assert cells is not None

        hashKey = getHashKey(hashKey)

        data = {'op': WebSocket.OP.UPDATE_ROW,
                'hashKey': hashKey,
                'cells': cells,
                'rowIndex': rowIndex,
                'rowClass' : rowClass}

        self.send(data)
        return hashKey

    def setHeader(self, cells, rowClass = 'row-fluid'):
        assert cells is not None

        data = {'op': WebSocket.OP.SET_HEADER,
                'cells' : cells,
                'rowClass' : rowClass}

        self.send(data)

    def removeItem(self, hashKey):
        assert hashKey is not None

        hashKey = hash(hashKey)

        data = {'op': WebSocket.OP.REMOVE_ITEM,
                'hashKey': hashKey}

        self.send(data)
        return hashKey