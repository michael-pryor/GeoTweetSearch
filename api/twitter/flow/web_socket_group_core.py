from abc import ABCMeta, abstractmethod, abstractproperty
import logging
from threading import RLock
import threading
from bottle import request, abort
import gevent
from api.config import Configuration
from api.core.signals.events import MultiEventSignaler, EventHandler, EventSignaler
from api.core.utility import packArguments, criticalSection
from api.twitter.flow.display_core import AsyncTunnelProvider
from api.web.config import WEBSITE_ROOT_WEBSOCKET
from api.web.web_core import WebApplication
from api.web.web_socket import WebSocket
from api.web.web_utility import SignalActions

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class WebSocketManager(object):
    __metaclass__ = ABCMeta

    def __init__(self, key, route, application):
        #super(WebSocketManager,self).__init__() <- don't know why it expects an argument (bug in python?)

        bottleRoute, link = route

        self.socket_route = bottleRoute
        self.socket_link = WEBSITE_ROOT_WEBSOCKET + link
        self.application = application
        self.key = key

        logger.info('Setting up web socket with route: %s' % self.socket_route)
        self.application.bottle_app.route(path=self.socket_route, callback=self.processWebSocketRoute)

    def getLink(self, *args, **kwargs):
        packed = packArguments(*args, **kwargs)
        if len(packed) > 0:
            return self.socket_link % packed
        else:
            return self.socket_link

    def getTemplateLink(self, *args, **kwargs):
        return {'ws_link_' + self.key: self.getLink(*args, **kwargs)}

    def onSocketRegistered(self, handler, signaler, tupleArguments):
        pass

    @abstractmethod
    def setupSocket(self, webSocket, tupleArguments):
        pass

    @abstractmethod
    def cleanupSocket(self, webSocket, tupleArguments):
        pass

    def getControl(self):
        raise NotImplementedError()

    def getControls(self):
        return [self.getControl()]

    def getArguments(self):
        return None

    def processWebSocketRoute(self, *args, **kwargs):
        """ Generic web socket processing.

            Registers socket with display handler. """
        wsock = request.environ.get('wsgi.websocket')
        if not wsock:
            abort(400, 'Expected WebSocket request.')

        customArguments = self.getArguments()
        if customArguments is not None:
            kwargs.update(customArguments)

        tupleArguments = packArguments(*args, **kwargs)
        assert tupleArguments is not None

        def onRegisteredFunc(handler, signaler):
            self.onSocketRegistered(handler, signaler, tupleArguments)

        # Use our own object has some extra features.
        wsock = WebSocket(webSocket=wsock, onRegisteredFunc=onRegisteredFunc)

        # Register controls
        wsock.addControls(self.getControls())
        try:
            if self.setupSocket(wsock, tupleArguments) is False:
                return

            while True:
                gevent.sleep(5)

                if wsock.is_cleaned_up:
                    break

                wsock.ping()

                if wsock.is_cleaned_up:
                    break
        finally:
            self.cleanupSocket(wsock, tupleArguments)

        logger.debug('Web socket terminated')

class WebSocketGroup(WebSocketManager, EventHandler, MultiEventSignaler):
    __metaclass__ = ABCMeta

    def __init__(self, key, route, application, signalers=None, preprocessSignal=None):
        WebSocketManager.__init__(self, key, route, application)
        EventHandler.__init__(self, processSignalFunc=self._processSignal, instant=False, signalers=signalers, preprocessSignal=preprocessSignal)
        MultiEventSignaler.__init__(self, key=key)

        assert isinstance(application, WebApplication)

    def _processSignal(self, signaler, data):
        # It simplifies the implementation if signalers cannot be added while we process signals.
        return criticalSection(self._signalers_lock,lambda: self.processSignal(signaler, data))

    @abstractmethod
    def processSignal(self, signaler, data):
        pass

    def onSocketRegistered(self, handler, signaler, tupleArguments):
        return self.pushInitialData(handler, signaler, tupleArguments)

    def setupSocket(self, webSocket, tupleArguments):
        # Web socket listens for signals from display object.
        self.registerHandler(handler=webSocket, key=tupleArguments)

    def cleanupSocket(self, webSocket, tupleArguments):
        self.unregisterHandler(handler=webSocket, key=tupleArguments)

    @abstractmethod
    def pushInitialData(self, handler, signaler, tupleArguments):
        pass




class GenericWsg(WebSocketGroup):
    """ Web socket group designed to handle a single item of data from signalers i.e. an object or literal. """
    __metaclass__ = ABCMeta

    def __init__(self, key, application, signalers, route):
        super(GenericWsg,self).__init__(key=key, application=application, signalers=signalers, route=route, preprocessSignal=self._handlerCacheUpdate)

        self._signalDataPtrLock = RLock()
        self.signalDataPtr = None

    @abstractmethod
    def pushSocketDisplayChange(self, control, updatedItem, oldCachedValue, isInitialPush, signaler, signalerKey):
        """ Makes calls to the relevant control objects in response to the change in updatedItem.
            @param control          Dictionary of control objects associated with the parent web socket.
            @param oldCachedValue   Previously cached value, retrieved through call to extractCacheValueFromItem.
            @param updatedItem      Data which has updated.
            @param isInitialPush    True if this is a new web socket where no data has been pushed before.
            @param signalerKey      Key associated with the signaler which triggered this event. """
        pass

    @abstractmethod
    def extractDataFromSignal(self, signalData):
        """ Retrieves the useful data from signalData.
            @param signalData data associated with event. This will never be None and will always be valid.
            @return data, perhaps in the form of a dictionary or list. """
        pass

    @abstractmethod
    def extractItemFromData(self, data, signalerKey):
        """ Retrieves the relevant item from data.
            @param data             data generated by a previous extractDataFromSignal call.
                                    This may be in the form of a dictionary.
            @param signalerKey      key associated with signaler which triggered this event,
                                    this is useful if the item to be extracted depends on the signaler.
            @return an item from the data, usually an object or literal value of some sort. """
        pass

    def _extractItemFromData(self, data, signalerKey):
        if data is None:
            return None

        return self.extractItemFromData(data, signalerKey)

    def onSignalerActivity(self, signalerKey):
        """ We can use this to e.g. record last usage of a resource. """
        pass

    def extractCacheValueFromItem(self, value):
        """ With each web socket we cache a piece of data used to
            indicate the age or reliability of that data. When new data comes in
            we do a comparison to determine if we should send an update through that socket.

            This method extracts the data to cache in the web socket.

            @param value Item retrieved via extractItemFromData call.
            @return An object or literal which is useful when cached in a web socket.
                    It will be fed into isDifference to determine whether an update
                    should be triggered. """
        return value.timestamp

    def getComparisonValueFromCacheValue(self, cacheValue):
        """ Retrieve the value used by isDifference for comparison. Override this method if you want to modify
            how the value is retrieved but not the actual comparison which takes place.

            @param value retrieved from cache via extractCacheValueFromItem call.
            @return comparison value to be fed into isDifference. """
        return cacheValue

    def isDifference(self, newCachedValue, oldCachedValue):
        """ Received an item and compares it to determine if there is a difference
            which should require data to be sent through a web socket.
            @param updatedItem      New item's cache value, received through a call to extractCacheValueFromItem.
            @param cachedValue      A previously cached value (or None if there is no previous value)
                                    that was retrieved through a call to extractCacheValueFromItem. """

        # If you are not careful you can end up caching the same reference,
        # which is futile!
        assert newCachedValue is not oldCachedValue

        if newCachedValue is not None:
            newCachedValue = self.getComparisonValueFromCacheValue(newCachedValue)
        if oldCachedValue is not None:
            oldCachedValue = self.getComparisonValueFromCacheValue(oldCachedValue)

        if newCachedValue is None:
            return oldCachedValue is not None

        if oldCachedValue is None:
            return newCachedValue is not None

        # If the items are different then we don't want to process them,
        # we only care about one id.
        return oldCachedValue != newCachedValue

    def updateItemFromCacheValue(self, newItem, oldCacheValue):
        """ Override this if the contents of the new item should depend on the value cached from the previous
            signal. e.g. you may want to merge the data rather than totally overwrite (which is the default behaviour).

            Note if caching is disabled this will still be called for each signal but oldCacheValue will always be None.
            This enables swapping between instant and non instant without modifying code.

            Note that the logic is as follows:
            - Compare old cache value and new cache value directly from signals.
            - If a difference exists:
                - Update item using updateItemFromCacheValue
                - Cache the value of the updated item.

            @param newItem          the new item retrieved from a call to extractItemFromData.
            @param oldCacheValue    the value cached from the previous signal, or None if there was no previous signal.
            @return the updated item - the previous item passed in as newItem will be discarded. """
        return newItem

    @property
    def isCacheValueEnabled(self):
        return True

    @property
    def isGroupCacheEnabled(self):
        return True

    def getFromGroupCache(self, key):
        if not self.isGroupCacheEnabled:
            return None

        return self._extractItemFromData(self.signalDataPtr, key)

    def updateGroupCache(self, newValue):
        if not self.isGroupCacheEnabled:
            return newValue

        def doChange():
            self.signalDataPtr = newValue
            return newValue

        return criticalSection(self._signalDataPtrLock, doChange)

    def getInitialItem(self, signaler, key):
        return self.getFromGroupCache(key)

    def pushInitialData(self, handler, signaler, key):
        """ Called when a new web socket is created, is intended to
            send initial data to the client. """
        assert isinstance(handler, EventHandler)
        assert isinstance(signaler, EventSignaler)

        # Use local cached value if possible.
        if self.isCacheValueEnabled:
            # Get cache value from last signal.
            value = signaler.data_cache.get('cached_value',None)
        else:
            value = None

        # Otherwise retrieve initial item and store it in local cache.
        if value is None:
            value = self.getInitialItem(signaler, key)
            if value is None:
                return

            value = self.updateItemFromCacheValue(value, None)
            if value is None:
                return

            if self.isCacheValueEnabled:
                newCacheValue = self.extractCacheValueFromItem(value)
                signaler.data_cache['cached_value'] = newCacheValue

        pushDisplayChange = lambda control, data: self.pushSocketDisplayChange(control, value, None, True, signaler, key)

        handler.on_signal_func(signaler, {SignalActions.SOCKET: pushDisplayChange})
        logger.debug('Pushed initial data for key: %s, control: %s' % (key, self.key))

    def processSignal(self, originalSignaler, signalData):
        """ Called when new data is received. """
        data = self.updateGroupCache(self.extractDataFromSignal(signalData))

        # Look through all signalers, we don't care about those
        # which no web socket is registered with.
        for signalerKey, signaler in self.signalers.iteritems():
            self.onSignalerActivity(signalerKey)

            updatedItem = self._extractItemFromData(data,signalerKey)
            if updatedItem is None:
                continue

            signalUpdate = True
            oldCachedValue = None
            if self.isCacheValueEnabled:
                # Get cache value from last signal.
                oldCachedValue = signaler.data_cache.get('cached_value',None)

                # Get cache value from this signal.
                newCacheValue = self.extractCacheValueFromItem(updatedItem)

                # Determine if the signal data differs significantly.
                signalUpdate = self.isDifference(newCacheValue, oldCachedValue)
            else:
                oldCachedValue = None

            # If there is a change then push it to the web socket.
            if signalUpdate:
                # Update signal based on previous signal as required - enables us to merge data.
                updatedItem = self.updateItemFromCacheValue(updatedItem, oldCachedValue)

                # Cache the value of this most up to date item.
                if self.isCacheValueEnabled:
                    newCacheValue = self.extractCacheValueFromItem(updatedItem)
                    signaler.data_cache['cached_value'] = newCacheValue

                pushDisplayChange = lambda _updatedItem, _signaler, _key: lambda controls, data: self.pushSocketDisplayChange(controls, _updatedItem, oldCachedValue, False, _signaler, _key)
                pushDisplayChange = pushDisplayChange(updatedItem, signaler, signalerKey)
                self.signalEvent({SignalActions.SOCKET : pushDisplayChange}, signalerKey)
                #logger.debug('Pushed update for key: %s, control: %s' % (signalerKey, self.key))

    def _handlerCacheUpdate(self, handler, signaler, oldData, newData):
        return self.preprocessSignal(signaler, oldData, newData)

    def preprocessSignal(self, signaler, previousSignalData, newSignalData):
        """ Called when a signal is sent to this web socket group in order to be
            cached for a later processSignal call.

            You can safely modify the contents of previousSignalData and newSignalData within
            the context of the signaler/handler paradigm.

            @param previousSignalData   Any previous preprocessed signal cached for that signaler, None if no data
                                        exists e.g. if two signals come in between processSignal calls, on the first
                                        signal previousSignalData will be None and on the second signal
                                        previousSignalData will be the data of the previous preprocessed signal.
            @param newSignalData        The signal that triggered this call.
            @return signal data to be cached. When processSignal is called, this data will be processed. """
        return newSignalData


class GenericMultiDataWsg(GenericWsg):
    """ Web socket group designed to handle a multiple items of data from signalers i.e. a dictionary, list, set or other similar type. """
    __metaclass__ = ABCMeta

    def __init__(self,key,application, signalers, route):
        super(GenericMultiDataWsg,self).__init__(key=key,application=application,signalers=signalers,route=route)

    @abstractmethod
    def pushSocketDisplayChangeEx(self, control, addedItems, removedItems, isInitialPush, signalerKey):
        pass

    def getDifference(self, set1, set2):
        if set1 is None:
            return None

        if set2 is None:
            return set1

        return set1 - set2

    def isDifference(self, newCachedValue, oldCachedValue):
        if newCachedValue is None:
            return oldCachedValue is not None

        if oldCachedValue is None:
            return newCachedValue is not None

        return len(oldCachedValue ^ newCachedValue) > 0

    def getAddedItems(self,updatedItems,previousItems):
        return self.getDifference(updatedItems,previousItems)

    def getRemovedItems(self,updatedItems,previousItems):
        return self.getDifference(previousItems,updatedItems)

    def pushSocketDisplayChange(self, controls, updatedItem, oldCachedValue, isInitialPush, signaler, signalerKey):
        newItems = self.getAddedItems(updatedItem,oldCachedValue)
        removedItems = self.getRemovedItems(updatedItem,oldCachedValue)

        if (newItems is not None and len(newItems) > 0) or (removedItems is not None and len(removedItems)) > 0:
            self.pushSocketDisplayChangeEx(controls, newItems, removedItems, isInitialPush, signalerKey)

    def extractCacheValueFromItem(self, value):
        """ With each web socket we cache a piece of data used to
            indicate the age or reliability of that data. When new data comes in
            we do a comparison to determine if we should send an update through that socket.

            This method extracts the data to cache in the web socket.

            @param value Item retrieved via extractItemFromData call.
            @return An object or literal which is useful when cached in a web socket.
                    It will be fed into isDifference to determine whether an update
                    should be triggered. """
        return value

    @property
    def isCacheValueEnabled(self):
        return True


class GenericMultiDataStatelessWsg(GenericWsg):
    """ Web socket group designed to handle a multiple items of data from signalers i.e. a dictionary, list, set or other similar type. """
    __metaclass__ = ABCMeta

    def __init__(self, key, application, signalers, route):
        super(GenericMultiDataStatelessWsg,self).__init__(key=key,application=application,signalers=signalers,route=route)

    @abstractmethod
    def pushSocketDisplayChangeEx(self, control, addedItems, isInitialPush, signalerKey):
        pass

    def getNewItems(self,updatedItems):
        return updatedItems

    def pushSocketDisplayChange(self, controls, updatedItem, oldCachedValue, isInitialPush, signaler, signalerKey):
        assert oldCachedValue is None

        newItems = self.getNewItems(updatedItem)

        if len(newItems) > 0:
            self.pushSocketDisplayChangeEx(controls, newItems, isInitialPush, signalerKey)

    @property
    def isCacheValueEnabled(self):
        return True

class GenericWsgInstanced(GenericWsg):
    """ Hooks in methods which inform the instance that it is being used,
        every time a web socket action takes place.

        This allows us to clean up old unused instances so as not to waste
        resources. """
    __metaclass__ = ABCMeta

    def __init__(self, key, application, signalers, route):
        super(GenericWsgInstanced,self).__init__(key, application, signalers, route)

    @staticmethod
    def getInstanceFromSignalerKey(signalerKey):
        return signalerKey[0]

    def extractItemFromData(self, data, signalerKey):
        instance_key = self.getInstanceFromSignalerKey(signalerKey)
        instance = data.get(instance_key, dict())
        return self.continueExtractItemFromData(data, instance, signalerKey)

    @abstractmethod
    def continueExtractItemFromData(self, data, instanceData, signalerKey):
        pass

    def onSignalerActivity(self, signalerKey):
        """ This stops the instance from being cleaned up. It has the impact of: if no clients connect
            in a while then the instance is cleaned up, otherwise it is kept alive. """
        instance_key = self.getInstanceFromSignalerKey(signalerKey)
        twitterInstance = self.application.twitter_instances.getInstanceByInstanceKey(instance_key)
        if twitterInstance is not None:
            twitterInstance.touch()




class WebSocketManagerDataProvider(WebSocketManager):
    __metaclass__ = ABCMeta

    def __init__(self, key, route, application, asyncTunnelProvider):
        super(WebSocketManagerDataProvider, self).__init__(key, route, application)

        assert isinstance(asyncTunnelProvider, AsyncTunnelProvider)
        self.async_tunnel_provider = asyncTunnelProvider

    @abstractmethod
    def initialiseTunnelSlots(self, webSocket):
        """ Initialize tunnel slots in tunnels_events, you can use
            the helper method initializeTunnelSlot. """
        pass

    @abstractmethod
    def manageSocket(self, webSocket, tupleArguments, socketId):
        """ Called when socket and tunnels are loaded and ready
            to be used. """
        pass

    @abstractmethod
    def onSocketId(self, webSocket, socketId, tupleArguments):
        """ Called when the socket ID is loaded but before tunnels
            are fully formed. The ID should be forwarded to the client
            so that it can create the tunnel so that we can complete
            the initialization process. """
        pass

    @property
    def requireAllTunnelsOpen(self):
        """ If all tunnels should be open during initialisation (setupSocket) then this
            should be true. If false then setupSocket doesn't open tunnels and you need
            to manually do this in manageSocket. """
        return True

    def initialiseTunnelSlot(self, tunnelId, webSocket):
        """ Initialize tunnel slot so that it may later be filled
            with a fully formed tunnel. """
        webSocket.tunnel_events[tunnelId] = threading.Event()

    def openTunnel(self, tunnelId, webSocket):
        """ Open an individual tunnel, the tunnel's slot must have
            already been initialized with initialise tunnel slot.

            If the tunnel is already open this will return instantly,
            otherwise it will wait for the tunnel to be opened by the client.

            If the web socket disconnects in this time the method will
            return safely.

            @return true if tunnel was created successfully and is now
            fully formed and ready to use. False if something went wrong. """
        socketId = webSocket.socket_id_in_provider
        tunnelEvent = webSocket.tunnel_events[tunnelId]

        logger.info('Attempting to open tunnel %s on socket %s' % (tunnelId, socketId))

        while tunnelEvent.wait(1) is False:
            webSocket.pingFreqLimited()

            if webSocket.is_cleaned_up:
                logger.info('Bulk data socket provider disconnecting, socket ID: %d' % socketId)
                return False

        if webSocket.tunnel_events.get(tunnelId,None) is None:
            logger.error('Tunnel marked as loaded by provider but is not, socket ID: %d' % socketId)
            return False

        logger.info('Successfully opened tunnel %s on socket %s' % (tunnelId, socketId))
        return True

    def openTunnels(self, webSocket):
        """ Makes calls to open tunnel until all tunnels are open,
            fully formed and ready to use."""
        for tunnelId in webSocket.tunnel_events.keys():
            if self.openTunnel(tunnelId, webSocket) is False:
                return False

        return True

    def sendDataOnTunnel(self, webSocket, tunnelId, data, close=False):
        tunnel = webSocket.tunnels.get(tunnelId,None)
        if tunnel is None:
            logger.error('Attempt was made to send data on tunnel with invalid ID: %s' % tunnelId)
            return

        tunnel.on_data(data)
        if close:
            tunnel.on_finish()

    def closeTunnel(self, webSocket, tunnelId):
        """ Close tunnel so that it is disconnected and future calls to
            openTunnel will block. """
        tunnel = webSocket.tunnels.get(tunnelId,None)
        if tunnel is None:
            return

        tunnel.on_finish()
        webSocket.tunnels[tunnelId] = None
        webSocket.tunnel_events[tunnelId].clear()

    def closeTunnels(self, webSocket):
        for tunnelId in webSocket.tunnel_events.keys():
            self.closeTunnel(webSocket, tunnelId)

    def setupSocket(self, webSocket, tupleArguments):
        webSocket.tunnels = dict()
        webSocket.tunnel_events = dict()

        # Initialise events which provider will use to notify us
        # when it has initialised the tunnels.
        self.initialiseTunnelSlots(webSocket)

        # Tell download provider that we want tunnels.
        socketId = self.async_tunnel_provider.addWebSocket(webSocket)
        webSocket.socket_id_in_provider = socketId
        self.onSocketId(webSocket, socketId, tupleArguments)

        # Wait for all tunnels to be loaded.
        if self.requireAllTunnelsOpen:
            if not self.openTunnels(webSocket):
                return False

        self.manageSocket(webSocket, tupleArguments, socketId)

        # We want to cleanup everything now since we are done.
        return False

    def cleanupSocket(self, webSocket, tupleArguments):
        webSocket.unregisterFromAll()
        self.closeTunnels(webSocket)




class GenericMultiDataWsgInstanceBased(GenericWsgInstanced, GenericMultiDataWsg):
    def __init__(self, key, application, signalers, route):
        super(GenericMultiDataWsgInstanceBased,self).__init__(key, application, signalers, route)

class GenericMultiDataStatelessWsgInstanceBased(GenericWsgInstanced, GenericMultiDataStatelessWsg):
    def __init__(self, key, application, signalers, route):
        super(GenericMultiDataStatelessWsgInstanceBased,self).__init__(key, application, signalers, route)


