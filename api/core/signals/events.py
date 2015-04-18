import logging
from threading import Lock, RLock, Semaphore
import unittest
import gevent
from api.core.utility import  HashableImpl, isDifference

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

def extractHandler(handler):
    try:
        if not isinstance(handler, EventHandler):
            handler = handler.event_handler
    except AttributeError:
        pass

    assert isinstance(handler, EventHandler)
    return handler


def extractSignaler(signaler):
    try:
        if not isinstance(signaler, EventSignaler):
            signaler = signaler.event_signaler
    except AttributeError:
        pass

    assert isinstance(signaler, EventSignaler)
    return signaler


class EventHandler(HashableImpl):
    """ Event handlers are registered to event signalers. The signaler then
        signals an event and this triggers the onEvent method, passing data
        to the handlers. """

    def __init__(self, processSignalFunc,
                       onRegisteredFunc=None,
                       onUnregisteredFunc=None,
                       shouldHandleSignalFunc=None,
                       signalers=None,
                       instant=True,
                       preprocessSignal=None):
        """ Initialize event handler.

            @param processSignalFunc            Called when signal is processed either from cache or directly from
                                                the signaler, depending on the instant parameter. This should be a
                                                function with signature: processSignal(signaler, data).

            @param onRegisteredFunc             Called when this handler is registered to a signaler. This should be
                                                a function with signature: onRegisteredFunc(handler, signaler) where
                                                handler is a reference to this object.

            @param onUnregisteredFunc           Same as onRegisteredFunc but called when unregistered from signaler.

            @param shouldHandleSignalFunc       Called when a signal is initially received, before caching or
                                                processing. This should be a function with signature:
                                                shouldHandleSignalFunc(signaler, data). If true is returned
                                                the signal continues to caching or processing, if false is returned
                                                the signal is discarded silently.

                                                Note: the signal passed to this method will have passed through
                                                the preprocess stage.

            @param instant                      If true signals are cached - one signal per signaler with newer signals
                                                overwriting older ones. Signals are cached until a call to
                                                processCachedSignals is made, at which point they are processed as
                                                normal. If false signals are not cached and are passed straight to
                                                the processSignalFunc as they are received.

            @param preprocessSignal             Called when a signal is initially received (before any caching).
                                                This should be a function with signature:
                                                preprocessSignal(handler, signaler, oldData, newData) which returns the
                                                modified signal.

                                                Using this method a signaler can modify the default behaviour
                                                of overwriting existing cached signals.
                                                For example, it can join multiple signals together so that no
                                                data loss occurs between processCachedSignals calls. Note that this
                                                function is thread safe and can safely modify the contents of oldData
                                                and newData within the context of the handler/signaler paradigm. """
        HashableImpl.__init__(self)

        if onRegisteredFunc is None:
            onRegisteredFunc = lambda x, y: None

        if onUnregisteredFunc is None:
            onUnregisteredFunc = lambda x, y: None

        if shouldHandleSignalFunc is None:
            shouldHandleSignalFunc = lambda x, y: True

        if preprocessSignal is None:
            preprocessSignal = lambda handler, signaler, oldData, newData: newData

        self.registered_to_signalers = set()
        self.on_registered_func = onRegisteredFunc
        self.on_unregistered_func = onUnregisteredFunc
        self.should_handle_signal_func = shouldHandleSignalFunc
        self.instant = instant
        self.preprocess_signal = preprocessSignal
        self.on_signal_func = self._handleSignalDecider

        if not self.instant:
            self._signals_cache_lock = Lock()
            self._signals_cache = dict()

        self.on_process_func = processSignalFunc

        if signalers is not None:
            for signaler in signalers:
                extractSignaler(signaler).registerHandler(self)

    def _handleSignalDecider(self, signaler, data):
        if not self.instant:
            previousData = self._signals_cache.get(signaler, None)
        else:
            previousData = None

        data = self.preprocess_signal(self, signaler, previousData, data)

        if self.should_handle_signal_func(signaler, data):
            if self.instant:
                self.on_process_func(signaler, data)
            else:
                self._cacheSignal(signaler, data)

    def _onRegistered(self, signaler):
        assert isinstance(signaler, EventSignaler)
        self.registered_to_signalers.add(signaler)
        self.on_registered_func(self,signaler)

    def _onUnregistered(self, signaler):
        assert isinstance(signaler, EventSignaler)
        self.registered_to_signalers.remove(signaler)
        self.on_unregistered_func(self,signaler)

    def unregisterFromAll(self):
        """ Unregisters this event handler from all signalers,
            useful when cleaning up. """
        for signaler in set(self.registered_to_signalers):
            signaler.unregisterHandler(self)

    def _cacheSignal(self, signaler, data):
        """ Called when initial signal comes through,
            we cache this for later until processSignals is called.
            Only one change per signaler is accepted, with newer ones
            overwriting older. """

        # If instant, this method should never be called.
        assert not self.instant

        self._signals_cache_lock.acquire()
        try:
            self._signals_cache[signaler] = data
        finally:
            self._signals_cache_lock.release()

    def processCachedSignals(self):
        """ Process all signals received since the last processDataChanges call.
            Calls processSignal. """
        if self.instant:
            return

        self._signals_cache_lock.acquire()

        try:
            signalsCache = dict(self._signals_cache)
            self._signals_cache.clear()
        finally:
            self._signals_cache_lock.release()

        for signaler, data in signalsCache.iteritems():
            self.on_process_func(signaler, data)


class EventHandlerImpl(object):
    """ Implementation of EventHandler, can easily be sub classed. """

    def __init__(self, eventSignalers=None):
        object.__init__(self)
        self.event_handler = EventHandler(self.onSignal, self.onRegistered, self.onUnregistered, eventSignalers)

    def onSignal(self, signaler, data):
        """ You must override this in order to deal with signals. """
        raise NotImplementedError

    def onUnregistered(self, handler, signaler):
        """ Override this if you are interested in knowing when
            this handler has been unregistered with a signaler. """
        pass

    def onRegistered(self, handler, signaler):
        """ Override this if you are interested in knowing when
            this handler has been registered with a signaler. """
        pass


class EventSignaler(HashableImpl):
    """ Event handlers are registered to event signalers. The signaler then
    signals an event and this triggers the onEvent method, passing data
    to the handlers. """

    def __init__(self, key=None, handlers=None, onNoHandlers=None):
        HashableImpl.__init__(self)
        self.handlers = set()
        self._lock = Lock()
        self.key = key
        self.on_no_handlers = onNoHandlers

        if handlers is not None:
            for handler in handlers:
                self.registerHandler(handler)

    def isKey(self, key):
        assert isinstance(key, basestring)
        if len(key) == len(self.key):
            return key == self.key
        else:
            # This enables support for multi event signalers.
            return key.startswith(self.key + '_')

    def registerHandler(self, handler):
        """ Registers handler with this signaler.
            @param handler: Must be an instance of EventHandler or
            have an event_handler which is an instance of EventHandler. """
        handler = extractHandler(handler)

        self._lock.acquire()
        try:
            self.handlers.add(handler)
        finally:
            self._lock.release()

        handler._onRegistered(self)

    def unregisterHandler(self, handler):
        """ Unregisters handler from this signaler.
            @param handler: Must be an instance of EventHandler or
            have an event_handler which is an instance of EventHandler. """
        handler = extractHandler(handler)

        noHandlers = False

        unregistered = False
        self._lock.acquire()
        try:
            self.handlers.remove(handler)

            if self.on_no_handlers is not None and len(self.handlers) < 1:
                noHandlers = True
        except KeyError:
            pass
        else:
            unregistered = True
        finally:
            self._lock.release()

        if unregistered:
            handler._onUnregistered(self)

        if noHandlers:
            self.on_no_handlers()

    def signalEvent(self, data):
        """ Signals an event in all registered handlers.
            @param data data to pass to handlers, the format of
            this data is decided by the user, there is no set format. """
        self._lock.acquire()
        try:
            handlers = set(self.handlers)
        finally:
            self._lock.release()

        for handler in handlers:
            handler.on_signal_func(self, data)

    @property
    def data_cache(self):
        """ Optional method which lets users cache data specific to the signaler.
            This is particularly useful with multi signalers. """
        try:
            return self._data_cache
        except AttributeError:
            self._data_cache = dict()
            return self._data_cache


class EventController(EventHandler, EventSignaler):
    """ An event controller is both a handler and a signaler.
        It temporarily caches signals from the handler (one per handler)
        and when processSignals is called the signals filter through to
        the handlers. """

    def __init__(self, resultKey, processSignalFunc, signalers=None, handlers=None, instant=False):
        """ Analysis objects are both signalers and handlers.
            They handle data changes and produce new analysis.

            @param resultKey key to identify resulting analysis.
            @param processSignalFunc function to be called when signal is processed,
                   return value is signaled by this object.
            @param signalers data source signalers which signal this object.
            @param handlers handle signals from this object.
            @param instant if true then signals are not cached, they pass straight through to
                   our signal function. """
        EventHandler.__init__(self, self._controllerProcessSignal, signalers=signalers, instant=instant)
        EventSignaler.__init__(self, resultKey, handlers=handlers)

        self._controllerSignalFunc = processSignalFunc

    def _controllerProcessSignal(self, signaler, data):
        self.signalEvent(self._controllerSignalFunc(signaler, data))

class MultiEventSignaler(HashableImpl):
    def __init__(self, key=None, handlers=None):
        HashableImpl.__init__(self)
        self.signalers = dict()
        self._signalers_lock = RLock()
        self.key = key

        if handlers is not None:
            for handler in handlers:
                self.registerHandler(handler)

    @staticmethod
    def getGeneralKeyString(key):
        try:
            return u'_'.join(unicode(x) for x in key)
        except TypeError:
            return unicode(key)

    def getKeyString(self, key):
        return self.key + '_' + MultiEventSignaler.getGeneralKeyString(key)

    def registerHandler(self, handler, key=None):
        handler = extractHandler(handler)

        if key is None:
            key = tuple()

        def onNoHandlers(lock, signalers):
            """ Called when signaler has no more handlers. This
                is important to avoid a memory leak. """
            logger.debug('Signaler for key %s being cleaned up' % self.getKeyString(key))

            lock.acquire()
            try:
                del signalers[key]
            finally:
                lock.release()

        onNoHandlersFunc = lambda _lock, _signalers: lambda: onNoHandlers(_lock, _signalers)
        onNoHandlersFunc = onNoHandlersFunc(self._signalers_lock, self.signalers)
        self._signalers_lock.acquire()
        try:
            # Create or reuse the signaler.
            signaler = self.signalers.setdefault(key,EventSignaler(key=self.getKeyString(key),onNoHandlers=onNoHandlersFunc))
            assert isinstance(signaler, EventSignaler)
        finally:
            self._signalers_lock.release()

        # Register handler with the signaler.
        signaler.registerHandler(handler)

    def getSignaler(self, key=None):
        if key is None:
            key = tuple()

        self._signalers_lock.acquire()
        try:
            signaler = self.signalers[key]
        except KeyError:
            return None
        else:
            assert isinstance(signaler,EventSignaler)
            return signaler
        finally:
            self._signalers_lock.release()

    def unregisterHandler(self, handler, key=None):
        handler = extractHandler(handler)
        signaler = self.getSignaler(key)
        if signaler is not None:
            signaler.unregisterHandler(handler)

    def signalEvent(self, data, key=None):
        signaler = self.getSignaler(key)
        if signaler is not None:
            signaler.signalEvent(data)
            return True
        else:
            return False

def updateSetAndSignal(oldSet, newSet, signaler):
    if isDifference(oldSet, newSet):
        signaler.signalEvent(newSet)

    return newSet


class testEvents(unittest.TestCase):
    class myHandler(EventHandlerImpl):
        def __init__(self,id=None):
            super(testEvents.myHandler,self).__init__()
            self.id = id

        def onSignal(self, signaler, data):
            logger.info('Data received by event handler %s with ID %s from signaler %s: %s' % (self.event_handler, self.id, signaler, data))

        def onRegistered(self, handler, signaler):
            assert handler is self.event_handler
            logger.info('Event handler %s with ID %s registered to signaler %s' % (self.event_handler, self.id, signaler))

        def onUnregistered(self, handler, signaler):
            assert handler is self.event_handler
            logger.info('Event handler %s with ID %s unregistered from signaler %s' % (self.event_handler, self.id, signaler))


    def testFlow(self):
        handler1 = testEvents.myHandler()
        handler2 = testEvents.myHandler()

        signaler1 = EventSignaler()
        signaler2 = EventSignaler()

        signaler1.registerHandler(handler1)

        signaler2.registerHandler(handler1)
        signaler2.registerHandler(handler2)

        signaler2.signalEvent('hello world, I am signaler 2')
        signaler1.signalEvent('hello universe, I am signaler 1')
        handler1.event_handler.unregisterFromAll()

        signaler1.signalEvent('nobody should hear me :(')

    def testMultiEventSignaler(self):
        signaler = MultiEventSignaler(key='test')

        argumentTuple1 = (50,100)
        argumentTuple2 = (50,200)
        argumentTuple3 = (500,500)
        argument = 2205348087

        signaler.registerHandler(testEvents.myHandler(argumentTuple1),argumentTuple1)
        signaler.registerHandler(testEvents.myHandler(argumentTuple2),argumentTuple2)
        signaler.registerHandler(testEvents.myHandler(argument),argument)

        handler = testEvents.myHandler(argumentTuple3)
        signaler.registerHandler(handler,argumentTuple3)

        assert signaler.signalEvent({'hello' : 'world'},(500,500)) is True
        assert signaler.signalEvent({'hello' : 'universe'},(50,100)) is True
        assert len(signaler.signalers) == 4
        handler.event_handler.unregisterFromAll()

        assert signaler.signalEvent({'hello' : 'universe'},(500,500)) is False
        assert signaler.signalEvent({'hello' : 'universe'},(499,499)) is False

        assert signaler.signalEvent({'hello' : 'universe'},2205348087) is True

        assert len(signaler.signalers) == 3
