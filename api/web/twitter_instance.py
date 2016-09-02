import json
import logging
from threading import RLock
import time
from api.caching.instance_codes import consumeCode, unconsumeCode
from api.caching.instance_lifetime import removeInstance, addInstance, setInstanceTemporalSourceLastTime
from api.caching.temporal_analytics import getTemporalInfluenceCollection, addTemporalEntry
from api.caching.tweet_user import getUserCollection, getTweetCollection
from api.config import Configuration
from api.core.data_structures.timestamp import Timestamped
from api.core.threads import startTwitterThread
from api.core.threads_core import BaseThread
from api.core.utility import criticalSection, getUniqueId, joinStringsToLengthPretty, joinStringsGrammarPretty, joinListOfLists, splitList, getEpochMs
from api.geocode.geocode_shared import GeocodeResultAbstract
from api.twitter.feed import TwitterAuthentication, TwitterSession
from api.twitter.flow.data_core import DataCollection

logger = logging.getLogger(__name__)


INFLUENCE_SOURCE = 1
GEOGRAPHICAL_FILTER = 2
INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER = 3

RECTANGLE_TYPE = 1
MARKER_TYPE = 2

def processRegionJsonString(regionJsonString):
    regionJson = json.loads(regionJsonString)

    results = {}

    for item in regionJson:
        displayType, entityType, coords, extraData = item
        byDisplayType = results.setdefault(displayType,dict())
        byEntityType = byDisplayType.setdefault(entityType, list())
        byEntityType.append({'coords' : coords, 'extra_data' : extraData})

    return results

def getInfluenceSourceRectangles(processedRegionJson):
    rectangleType = processedRegionJson.get(RECTANGLE_TYPE,None)
    if rectangleType is None:
        return list()

    result =  rectangleType.get(INFLUENCE_SOURCE,list())
    result += rectangleType.get(INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER,list())
    return result

def getInfluenceSourceMarkers(processedRegionJson):
    markerType =  processedRegionJson.get(MARKER_TYPE,None)
    if markerType is None:
        return list()

    results = markerType.get(INFLUENCE_SOURCE,list())
    results += markerType.get(INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER,list())
    return results

def getInfluenceSourceIdsFromMarkers(markers):
    results = list()
    for item in markers:
        results.append(item['extra_data']['cacheId'])

    return results

def getCoordsFromItems(items):
    results = list()
    for item in items:
        results.append(item['coords'])
    return results

def formatCoordsForTwitter(coords):
    return splitList(joinListOfLists(coords),2)

def getGeographicalFilterRectangles(processedRegionJson):
    rectType =  processedRegionJson.get(RECTANGLE_TYPE,None)
    if rectType is None:
        return list()

    return rectType.get(GEOGRAPHICAL_FILTER,list()) + rectType.get(INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER,list())


class TwitterInstance(Timestamped):
    def __init__(self,
                 instanceKey,
                 parentTwitterInstances,
                 twitterAuthentication,
                 geographicSetupString,
                 keywords,
                 instanceSetupCode,
                 startTime = None,
                 lastTemporalTimeIdBySource = None,
                 isCritical = False):
        super(TwitterInstance, self).__init__(startTime)

        logger.debug('Instance is %dms old' % self.construct_age)

        assert isinstance(parentTwitterInstances,TwitterInstances)
        assert isinstance(twitterAuthentication,TwitterAuthentication)

        if lastTemporalTimeIdBySource is None:
            lastTemporalTimeIdBySource = dict()

        if instanceSetupCode is None or len(instanceSetupCode) == 0:
            self.enable_shutdown_after_no_usage = True
            self.instance_setup_code = None
        else:
            codeValid = consumeCode(instanceSetupCode)
            if codeValid:
                logger.info('Instance %s has loaded setup code %s' % (instanceKey, instanceSetupCode))
                self.instance_setup_code = instanceSetupCode
                self.enable_shutdown_after_no_usage = False
            else:
                logger.warn('Instance %s was provided with an invalid setup code: %s' % (instanceKey, instanceSetupCode))
                raise ValueError('Invalid setup code: %s' % unicode(instanceSetupCode))

        self.twitter_authentication = twitterAuthentication
        self.oauth = TwitterInstance.makeAuthTuple(twitterAuthentication.access_token, twitterAuthentication.access_secret)
        self.instance_key = instanceKey

        self.geographic_setup_string = geographicSetupString
        self.parent_twitter_instances = parentTwitterInstances

        self.region_json = processRegionJsonString(self.geographic_setup_string)
        self.geographical_filter_rectangles = formatCoordsForTwitter(getCoordsFromItems(getGeographicalFilterRectangles(self.region_json)))
        self.influence_source_rectangles = getCoordsFromItems(getInfluenceSourceRectangles(self.region_json))
        self.influence_source_cache_ids = getInfluenceSourceIdsFromMarkers(getInfluenceSourceMarkers(self.region_json))

        self.keywords = keywords

        self.is_shutdown = False

        self.last_temporal_time_id_by_source = lastTemporalTimeIdBySource

        # Add first so that we only try to set this up one at a time.
        # i.e. if instance takes an hour to start up several requests come in
        # but we start that instance only once and subsequent requests are ignored.
        self.parent_twitter_instances.add(self)
        try:
            twitterThread = startTwitterThread(self)

            self.twitter_thread = twitterThread
            self.setup_error = None
        except TwitterSession.SessionException as e:
            problemStr = 'Failed to establish twitter connection to streaming API with oauth: %s - instance could not be started, reason: %s' % (unicode(self.oauth), e)
            logger.error(problemStr)

            if isCritical:
                raise Exception('Instance failed to startup while starting server')

            self.shutdownInstance()
            self.setup_error = problemStr
            return

        addInstance(self.instance_key,
                    self.twitter_authentication.access_token,
                    self.twitter_authentication.access_secret,
                    self.geographic_setup_string,
                    self.keywords,
                    self.instance_setup_code,
                    self.constructed_at)


    @staticmethod
    def makeAuthTuple(oauthToken, oauthSecret):
        return oauthToken, oauthSecret

    def getShortDescription(self, capital):
        def doCapital():
            if capital:
                return 'L' + self._short_description
            else:
                return 'l' + self._short_description

        try:
            return doCapital()
        except AttributeError:
            instanceKeywords = self.twitter_thread.twitter_feed.keywords
            instanceNumGeographicAreas = len(self.twitter_thread.twitter_feed.locations) / 2 # divide by two because each area has two coordinates.
            numInfluenceAreas = len(self.influence_source_rectangles)
            numInfluenceLocations = len(self.influence_source_cache_ids)

            if instanceKeywords is not None and len(instanceKeywords) > 0:
                keywordsString = 'keywords: %s' % joinStringsToLengthPretty(instanceKeywords,Configuration.INSTANCE_SHORT_DESCRIPTION_KEYWORDS_MAX_LENGTH)
            else:
                keywordsString = None

            if instanceNumGeographicAreas > 0:
                geographicString = '%d geographic area' % instanceNumGeographicAreas
                if instanceNumGeographicAreas > 1:
                    geographicString += 's'
            else:
                geographicString = None

            if numInfluenceLocations > 0:
                influenceLocationsString = '%d influence source location' % numInfluenceLocations
                if numInfluenceLocations > 1:
                    influenceLocationsString += 's'
            else:
                influenceLocationsString = None

            if numInfluenceAreas > 0:
                influenceAreasString = '%d influence source area' % numInfluenceAreas
                if numInfluenceAreas > 1:
                    influenceAreasString += 's'
            else:
                influenceAreasString = None

            self._short_description = 'ooking at %s' % joinStringsGrammarPretty([keywordsString, geographicString, influenceLocationsString, influenceAreasString])
            return doCapital()

    def shutdownInstance(self, removeFromTwitterInstancesParent = True):
        if self.is_shutdown:
            return

        if removeFromTwitterInstancesParent and self.parent_twitter_instances is not None:
            # Will call this method with removeFromTwitterInstancesParent set to False.
            self.parent_twitter_instances.removeTwitterInstanceByAuth(self.oauth)
        else:
            self.is_shutdown = True

            instanceKey = unicode(self.instance_key)
            logger.info('Shutdown instance called on instance %s' % instanceKey)

            logger.info('Shutting down twitter thread on instance %s..' % instanceKey)
            try:
                self.twitter_thread.stop()
            # might not have been initialized yet.
            except AttributeError:
                pass

            # Don't wait on thread, cannot find a way to terminate post request in requests API so have
            # to wait for next tweet or keep alive request to come from twitter before terminating.
            #self.twitter_thread.join()

            # Wait for current write to finish, avoid dropping collection and then when write completes
            # collection is made again.
            time.sleep(1.5)

            logger.info('Dropping twitter user data on instance %s..' % instanceKey)
            getUserCollection(instanceKey).drop()

            logger.info('Dropping twitter tweet data on instance %s..' % instanceKey)
            getTweetCollection(instanceKey).drop()

            logger.info('Dropping twitter temporal influence data on instance %s..' % instanceKey)
            getTemporalInfluenceCollection(instanceKey).drop()

            if self.instance_setup_code is not None:
                logger.info('Returning instance setup code %s on instance %s..' % (instanceKey, self.instance_setup_code))
                unconsumeCode(self.instance_setup_code)

            logger.info('Removing instance from instance %s lifetime collection..' % instanceKey)
            removeInstance(instanceKey)

            logger.info('Instance %s cleaned up successfully' % instanceKey)

    def addTemporalEntry(self, temporalCollection, timeId, userProviderId, userPlaceId, followerProviderId, followerPlaceId, followerPlaceType):
        if self.is_shutdown:
            return

        tupleUserCacheId = GeocodeResultAbstract.buildCacheIdTuple(userProviderId, userPlaceId)
        dictUserCacheId = GeocodeResultAbstract.buildCacheId(userProviderId, userPlaceId)
        lastTimeId = self.last_temporal_time_id_by_source.get(tupleUserCacheId,None)

        destination = '%s_%s' % (followerPlaceType, followerPlaceId)
        addTemporalEntry(temporalCollection, lastTimeId, timeId, dictUserCacheId, destination, followerProviderId)

        self.last_temporal_time_id_by_source[tupleUserCacheId] = timeId
        setInstanceTemporalSourceLastTime(self.instance_key, userProviderId, userPlaceId, timeId)



class TwitterInstances(object):
    def __init__(self, dataCollection, tweetProvider):
        super(TwitterInstances, self).__init__()
        assert isinstance(dataCollection, DataCollection)

        self._by_oauth = dict()
        self._by_instance_key = dict()
        self._lock = RLock()
        self.data_collection = dataCollection
        self.tweet_provider = tweetProvider

    def add(self, twitterInstance):
        assert isinstance(twitterInstance, TwitterInstance)

        self._lock.acquire()
        try:
            self._by_instance_key[twitterInstance.instance_key] = twitterInstance
            self._by_oauth[twitterInstance.oauth] = twitterInstance
        finally:
            self._lock.release()

    def getUniqueInstanceKey(self):
        def func():
            instanceKey = unicode(getUniqueId())
            while instanceKey in self._by_instance_key:
                instanceKey = unicode(getUniqueId())
            return instanceKey

        return criticalSection(self._lock, func)

    def createInstance(self, twitterAuthentication, geographic_setup_string, keywords, instance_setup_code):
        def func():
            twitterInstance = TwitterInstance(self.getUniqueInstanceKey(),
                                              self,
                                              twitterAuthentication,
                                              geographic_setup_string,
                                              keywords,
                                              instance_setup_code)

            return twitterInstance

        return criticalSection(self._lock, func)

    def getInstanceList(self):
        return criticalSection(self._lock, lambda: list(self._by_instance_key.values()))

    def isInstanceKeyInUse(self, instanceKey):
        return criticalSection(self._lock, lambda: instanceKey in self._by_instance_key)

    def isAuthInUse(self, oauth):
        return criticalSection(self._lock, lambda: oauth in self._by_oauth)

    def getInstanceByInstanceKey(self, instanceKey):
        result = criticalSection(self._lock, lambda: self._by_instance_key.get(instanceKey, None))
        return result

    def getInstanceByAuth(self, oauth):
        result = criticalSection(self._lock, lambda: self._by_oauth.get(oauth, None))
        return result

    def removeTwitterInstanceByInstanceKey(self, instanceKey):
        self._lock.acquire()
        try:
            instance = self._by_instance_key.get(instanceKey)
            if instance is None:
                return None

            assert isinstance(instance, TwitterInstance)

            # Remove from dictionaries first so that it is no
            # longer accessible from the rest of the application.
            del self._by_instance_key[instanceKey]
            del self._by_oauth[instance.oauth]
        finally:
            self._lock.release()

        # Cleanup instance.
        instance.shutdownInstance(False)
        self.data_collection.removeInstanceData(instanceKey)

        return instance

    def removeTwitterInstanceByAuth(self, oauth):
        self._lock.acquire()
        try:
            instance = self._by_oauth.get(oauth)
            if instance is None:
                return None

            assert isinstance(instance, TwitterInstance)

            # Remove from dictionaries first so that it is no
            # longer accessible from the rest of the application.
            del self._by_oauth[oauth]
            del self._by_instance_key[instance.instance_key]

            print unicode(self._by_instance_key)
        finally:
            self._lock.release()

        # Cleanup instance.
        instance.shutdownInstance(False)
        self.data_collection.removeInstanceData(unicode(instance.instance_key))

        return instance


def restartTwitterInstanceByAuth(twitterInstances, auth):
    twitterInstance = twitterInstances.removeTwitterInstanceByAuth(auth)
    if twitterInstance is None:
        problemStr = 'Failed to remove instance with auth: %s' % unicode(auth)
        logger.error(problemStr)
        return None

    assert isinstance(twitterInstance,TwitterInstance)
    return TwitterInstance(twitterInstance.instance_key,
                           twitterInstance.parent_twitter_instances,
                           twitterInstance.twitter_authentication,
                           twitterInstance.geographic_setup_string,
                           twitterInstance.keywords,
                           twitterInstance.instance_setup_code)


def restartTwitterInstance(twitterInstances, twitterInstance):
    restartTwitterInstanceByAuth(twitterInstances, twitterInstance.oauth)

class TwitterInstancesPruner(BaseThread):
    """ This utility thread loops through all the twitter instances
        and checks when they were last used, cleaning up old ones. """

    def __init__(self, maxInactive, maxConstructAge, instances):
        super(TwitterInstancesPruner, self).__init__('TwitterInstancesPruner',
                                                     criticalThread = True)
        assert isinstance(instances, TwitterInstances)
        self.max_inactive = maxInactive
        self.max_construct_age = maxConstructAge
        self.instances = instances

    def _run(self):
        while True:
            copy = criticalSection(self.instances._lock, lambda: dict(self.instances._by_oauth))

            for oauth, instance in copy.iteritems():
                assert isinstance(instance, TwitterInstance)

                if instance.enable_shutdown_after_no_usage and instance.age > self.max_inactive:
                    # I want to see this in the error log.
                    logger.critical('Cleaning up instance with oauth: %s, it has been inactive for > %dms' % (unicode(oauth), self.max_inactive))
                    self.instances.removeTwitterInstanceByAuth(oauth)

                if instance.construct_age > self.max_construct_age:
                    logger.critical('Restarting instance with oauth: %s, it has been alive > %dms' % (unicode(oauth), self.max_construct_age))
                    result = restartTwitterInstanceByAuth(self.instances, oauth)
                    if result is not None:
                        logger.error('Failed to restart instance with oauth: %s, reason: %s' % (unicode(oauth),result))

            time.sleep(2)