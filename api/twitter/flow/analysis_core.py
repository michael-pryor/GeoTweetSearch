import logging
from api.core.signals.events import   EventController

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class Analysis(EventController):
    def __init__(self, resultKey, dataSignalers=None, displayHandlers=None):
        """ @param resultKey key to identify resulting analysis.
            @param dataSignalers data source signalers.
            @param displayHandlers display handlers. """
        EventController.__init__(self, resultKey, self.processDataChange, signalers=dataSignalers, handlers=displayHandlers)

    def processDataChange(self, signaler, data):
        raise NotImplementedError