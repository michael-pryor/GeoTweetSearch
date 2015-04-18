from abc import ABCMeta, abstractmethod
import logging
from threading import Thread
import urllib
from bottle import response
from api.config import Configuration
from api.core.signals.events import    EventHandler
from api.core.utility import getUniqueId, packArguments, Timer, doUrlEncode
from api.web.config import DEFAULT_TEMPLATE_ARGS, WEBSITE_ROOT_HTTP
from api.web.web_core import WebApplication
import gevent.queue
from api.web.web_socket import WebSocket

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class Display(EventHandler):
    class LinkInfo(object):
        def __init__(self, linkFunction, pageLink):
            super(Display.LinkInfo,self).__init__()
            self.link_function = linkFunction
            self.page_link = WEBSITE_ROOT_HTTP + pageLink

        @property
        def page_link_function(self):
            return self.link_function(self.page_link)

        def getPageLink(self,*args,**kwargs):
            return self.page_link_function(*args,**kwargs)

    link_info = None

    def __init__(self, application, pageRoute, signalers=None, webSocketManagers=None, onDisplayUsageFunc=None):
        EventHandler.__init__(self, processSignalFunc=self.processSignal, signalers=signalers, instant=False)

        assert isinstance(application, WebApplication)
        assert pageRoute is not None

        self.application = application

        self.page_route, method = pageRoute
        if method is None:
            method = ['GET', 'POST']

        logger.info('Setting up web page with route: %s, method: %s' % (self.page_route, method))
        self.application.bottle_app.route(path=self.page_route, callback=self._getPageHtml, method=method)

        self.web_socket_managers = webSocketManagers
        self.on_display_usage_func = onDisplayUsageFunc

    @property
    def page_html_function(self):
        raise NotImplementedError

    def getTemplateLinks(self, *args, **kwargs):
        dic = dict()

        if self.web_socket_managers:
            for webSocketManager in self.web_socket_managers:

                if isinstance(webSocketManager, tuple):
                    webSocketManager, includeFullTemplateLink = webSocketManager
                else:
                    includeFullTemplateLink = True

                # True if web socket follows same parameters as display e.g.
                # ws with param a,b,c will work with display a,b,c. But if
                # ws is d,e,f and display is a,b then won't work, so we include
                # link without parameters.
                if includeFullTemplateLink:
                    dic.update(webSocketManager.getTemplateLink(*args, **kwargs))
                else:
                    dic.update(webSocketManager.getTemplateLink())

        return dic

    def _getPageHtml(self, *args, **kwargs):
        if self.on_display_usage_func is not None:
            self.on_display_usage_func(self, packArguments(*args,**kwargs))

        dic = dict(DEFAULT_TEMPLATE_ARGS)
        dic.update(self.getTemplateLinks(*args, **kwargs))
        return self.page_html_function(templateArguments=dic, *args, **kwargs)

    def processSignal(self, signaler, data):
        raise NotImplementedError

    @staticmethod
    def getLink(linkAddress, text=None, target='_blank', javascript=None, linkId = None, htmlClass=None):
        if text is None:
            text = linkAddress

        assert target is not None and len(target) > 0

        if linkId is None:
            linkId = ''
        else:
            linkId = ' id="%s"' % linkId

        if javascript is None:
            javascript = ''
        else:
            javascript = ' onclick="%s"' % javascript

        if htmlClass is not None:
            htmlClassString = ' class="%s"' % htmlClass
        else:
            htmlClassString = ''

        return '<a href="%s"%s%s target="%s"%s>%s</a>' % (linkAddress, linkId, javascript, target, htmlClassString, text)

    @staticmethod
    def getImage(imageAddress, title=None, alternativeText=None, className=None):
        html = '<img src="%s"' % imageAddress
        if alternativeText is not None:
            html += ' alt="%s"' % alternativeText

        if title is None:
            title = alternativeText

        if title is not None:
            html += ' title="%s"' % title

        if className is not None:
            html += ' class="%s"' % className

        html += '>'

        return html

    @staticmethod
    def addArgumentsToLink(linkAddress, **kwargs):
        if len(kwargs) > 0:
            strToAppend = '?'

            for key, value in kwargs.iteritems():
                if value is not None:
                    if isinstance(value, basestring):
                        value = doUrlEncode(value)
                    else:
                        value = unicode(value)

                    strToAppend += unicode(key) + '=' + value + '&'

            strToAppend = strToAppend[:-1]
            return linkAddress + strToAppend
        else:
            return linkAddress


class AsyncWorker(Thread):
    DEFAULT_QUEUE_LENGTH = 4

    def __init__(self, queueLength=None, onDisplayUsageFunc=None):
        super(AsyncWorker, self).__init__()
        if queueLength is None:
            queueLength = AsyncWorker.DEFAULT_QUEUE_LENGTH

        self.queue = gevent.queue.Queue(queueLength)
        self.on_display_usage_func = onDisplayUsageFunc

    def on_data(self, chunk):
        if self.on_display_usage_func is not None:
            self.on_display_usage_func()
        return self.queue.put(chunk)

    def on_finish(self):
        if self.on_display_usage_func is not None:
            self.on_display_usage_func()
        return self.queue.put(StopIteration)


class AsyncTunnelProvider(Display):
    __metaclass__ = ABCMeta

    def __init__(self, application, pageRoute, onDisplayUsageFunc=None):
        Display.__init__(self, application, pageRoute, onDisplayUsageFunc=onDisplayUsageFunc)
        self.sockets = dict()

    def addWebSocket(self,socket,socketId=None):
        assert isinstance(socket, WebSocket)

        if socketId is None:
            socketId = self.getSocketId()

        def onSocketClose(socket):
            try:
                del self.sockets[socketId]
            except KeyError:
                pass

        self.sockets[socketId] = socket
        socket.cleanup_funcs.append(onSocketClose)
        return socketId

    def getSocketId(self):
        socketId = int(getUniqueId())

        while socketId in self.sockets:
            socketId = int(getUniqueId())

        return socketId

    @abstractmethod
    def setResponseHeaders(self, tunnelId):
        pass

    @property
    def page_html_function(self):
        def func(templateArguments, *args, **kwargs):
            if self.on_display_usage_func is not None:
                displayUsageFuncCallTimer = Timer(1000,True)

                def theDisplayUsageFunc():
                    if displayUsageFuncCallTimer.ticked():
                        self.on_display_usage_func(self,packArguments(*args,**kwargs))

                onDisplayUsageFunc = theDisplayUsageFunc
            else:
                onDisplayUsageFunc = None

            # > 1 for buffering, ensure we are always sending not send -> wait for database -> send.
            worker = AsyncWorker(2,onDisplayUsageFunc)

            tunnelId = kwargs['tunnel_id']
            socketId = kwargs['socket_id']
            self.setResponseHeaders(tunnelId)

            logger.info('Tunnel %s on socket %s has started opening' % (tunnelId, socketId))

            socket = self.sockets.get(socketId,None)
            if socket is None:
                logger.error('Bulk download attempted but no matching socket with ID: %d found' % socketId)
                worker.on_finish()
                return worker.queue

            tunnelEvent = socket.tunnel_events.get(tunnelId,None)
            if tunnelEvent is None:
                logger.error('Invalid tunnel ID received: %s' % tunnelId)
                worker.on_finish()
                return worker.queue

            if tunnelEvent.is_set():
                logger.error('Attempted to assign two bulk download providers to one socket with ID: %d, and tunnel ID: %s' % (socketId,tunnelId))
                worker.on_finish()
                return worker.queue

            socket.tunnels[tunnelId] = worker
            tunnelEvent.set()

            return worker.queue

        return func

class AsyncTunnelProviderFile(AsyncTunnelProvider):
    def __init__(self, application, pageRoute, onDisplayUsageFunc=None):
        super(AsyncTunnelProviderFile, self).__init__(application, pageRoute, onDisplayUsageFunc)

    def setResponseHeaders(self, tunnelId):
        response.content_type = 'data:text/csv;'
        header = 'attachment; filename="%s.%s"' % (self.getFileName(tunnelId), self.getFileExtension(tunnelId))
        logger.info('HEADER: %s' % header)
        response.headers['Content-Disposition'] = header

    def getFileName(self, tunnelId):
        return tunnelId

    def getFileExtension(self, tunnelId):
        return 'csv'