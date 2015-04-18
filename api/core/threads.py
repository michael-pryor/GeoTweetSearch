import copy
import logging
import os
from threading import Thread, RLock, Event
import threading
import time
import thread

from api.caching.temporal_analytics import getTimeIdFromTimestamp, getTemporalInfluenceCollection
from api.config import Configuration
from api.core.data_structures.queues import QueueEx, QueueNotify
from api.core.threads_core import BaseThread
from api.core.utility import DummyIterable, getUniqueId, criticalSection, getEpochMs, Timer
from api.geocode.geocode_cached import getGeocodeDataInMemoryCacheSize, getGeocodeQueryInMemoryCacheSize
from api.geocode.geocode_shared import GeocodeResultAbstract
from api.twitter.flow.data_core import DataCollection
from api.twitter.feed import Tweet, User, TwitterSession, TwitterFeed, UserAnalysis, Place, UserGeocodeConfig


logger = logging.getLogger(__name__)

def getUser(item):
    if isinstance(item, Tweet):
        return item.user
    elif isinstance(item, User):
        return item
    else:
        assert True

class TwitterThread(BaseThread):
    def __init__(self, feed, outputQueue=None, initialData=None):
        super(TwitterThread,self).__init__(self.__class__.__name__ + "_" + str(getUniqueId()),
                                           criticalThread = False)

        if feed is None:
            feed = TwitterFeed([],[],[],DummyIterable(),None)

        if outputQueue is None:
            outputQueue = QueueEx()

        assert isinstance(feed, TwitterFeed)
        assert isinstance(feed.twitter_session, TwitterSession)

        self.input_queue = feed
        self.twitter_session = feed.twitter_session
        self.twitter_feed = feed

        self.output_queue = outputQueue

        if initialData is not None:
            for item in initialData:
                item = copy.deepcopy(item)

                user = getUser(item)
                assert isinstance(user,User)

                logger.info('Retrieved tweet/user from file: %s' % item)

                item.setTwitterSession(self.twitter_session)

                self.output_queue.put(item)

        self.num_dropped = 0
        self.num_processed = 0
        self.num_twitter_geocoded_place = 0
        self.num_twitter_geocoded_coordinate = 0
        self.num_twitter_geocoded_both = 0
        self.num_not_twitter_geocoded = 0
        self.num_no_location = 0
        self.num_geocodeable = 0
        self.log_num_dropped_timer = Timer(Configuration.LOG_DROP_AMOUNT_FREQ_MS,False)

    def _onFailure(self, e):
        logger.error('Twitter stream thread has failed for instance %s, shutting down instance' % self.twitter_session.instance_key)
        self.twitter_session.parent_instance.shutdownInstance()
        super(TwitterThread,self)._onFailure(e)

    def _onRestart(self, e):
        logger.error('Twitter stream thread has failed for instance %s, restarting stream' % self.twitter_session.instance_key)
        self.twitter_feed.restartConnection()

    def _run(self):
        for tweet in self.input_queue:
            if self.stopped:
                return 0

            if tweet is None:
                continue

            if self.log_num_dropped_timer.ticked():
                numProcessed = self.num_processed
                numDropped = self.num_dropped
                total = numProcessed + numDropped
                if total == 0:
                    percentageDropped = 0
                else:
                    percentageDropped = float(numDropped) / float(total) * 100.0
                outputQueueSize = self.output_queue.qsize()

                numNoLocation = self.num_no_location
                numTwitterGeocodedPlace = self.num_twitter_geocoded_place
                numTwitterGeocodedCoordinate = self.num_twitter_geocoded_coordinate
                numTwitterGeocodedBoth = self.num_twitter_geocoded_both
                numNotTwitterGeocoded = self.num_not_twitter_geocoded
                numGeocodeable = self.num_geocodeable

                self.num_no_location = 0
                self.num_twitter_geocoded_place = 0
                self.num_twitter_geocoded_coordinate = 0
                self.num_twitter_geocoded_both = 0
                self.num_not_twitter_geocoded = 0
                self.num_geocodeable = 0

                self.num_dropped = 0
                self.num_processed = 0

                # GCQ = geocode cache queue.
                logger.info('Processed %d items, dropped %d items (%.2f%%) from GCQ (queue size: %d)' % (numProcessed, numDropped, percentageDropped, outputQueueSize))

                logger.info('Initial tweet state: no twitter geocode %d, twitter place %d, twitter coord %d, twitter place and coord %d, num geocodeable %d, num not geocodeable %d' % (numNotTwitterGeocoded, numTwitterGeocodedPlace, numTwitterGeocodedCoordinate, numTwitterGeocodedBoth, numGeocodeable, numNoLocation))

            assert isinstance(tweet, Tweet)

            if tweet.has_twitter_place and tweet.coordinate is None:
                self.num_twitter_geocoded_place += 1
            elif tweet.coordinate is not None and not tweet.has_twitter_place:
                self.num_twitter_geocoded_coordinate += 1
            elif tweet.coordinate is not None and tweet.has_twitter_place:
                self.num_twitter_geocoded_both += 1
            else:
                self.num_not_twitter_geocoded += 1

            if tweet.has_user:
                if (not tweet.user.has_location) and tweet.coordinate is None and (not tweet.has_twitter_place):
                    self.num_no_location += 1
                else:
                    self.num_geocodeable += 1

                if self.output_queue.qsize() < Configuration.GEOCODE_FROM_CACHE_INPUT_THREAD_SIZE_CAP:
                    self.num_processed += 1
                    self.output_queue.put(tweet)
                else:
                    self.num_dropped += 1

    def stop(self):
        super(TwitterThread,self).stop()
        if self.twitter_session is not None:
            self.twitter_session.close()


def processGeocodedUser(user, requiredType):
    assert isinstance(user, User)
    if not user.is_geocoded:
        return None

    if user.location_geocode.place_type != requiredType:
        return None

    return user

class GeocodeFromCacheThread(BaseThread):
    def __init__(self,
                 geocodeConfig,
                 inputQueue=None,
                 successOutputQueue=None,
                 primaryFailureOutputQueue=None,
                 highLoadFailureOutputQueue=None,
                 inMemoryOnly=None):
        if inMemoryOnly:
            inMemoryOnlyStr = '_MEMORY_ONLY'
        else:
            inMemoryOnlyStr = ''

        super(GeocodeFromCacheThread,self).__init__('%s%s' % (self.__class__.__name__, inMemoryOnlyStr),
                                                    criticalThread = True)

        assert isinstance(geocodeConfig, UserGeocodeConfig)

        if inputQueue is None:
            inputQueue = QueueEx()
        if successOutputQueue is None:
            successOutputQueue = QueueEx()
        if primaryFailureOutputQueue is None:
            primaryFailureOutputQueue = QueueEx()

        self.input_queue = inputQueue
        self.success_output_queue = successOutputQueue
        self.primary_failure_output_queue = primaryFailureOutputQueue
        self.high_load_failure_output_queue = highLoadFailureOutputQueue
        self.geocode_config = geocodeConfig

        self.num_dropped_from_success = 0
        self.num_dropped_from_primary_failure = 0
        self.num_failed_over = 0
        self.log_timer = Timer(Configuration.LOG_DROP_AMOUNT_FREQ_MS,False)

        self.num_processed = 0
        self.in_memory_only = inMemoryOnly

        self.sleep_time = float(Configuration.GEOCODE_FROM_CACHE_THREAD_WAIT_TIME_MS) / 1000.0

    def _run(self):
        for item in self.input_queue:
            if not self.in_memory_only:
                time.sleep(self.sleep_time)

            user = getUser(item)
            assert user is not None

            user.clearGeocode(True) # in case previously geocoded by in memory.

            if user.is_geocoded:
                success = True
            else:
                success = user.geocodeLocationFromCache(self.geocode_config, self.in_memory_only)

            if self.log_timer.ticked():
                numProcessed = self.num_processed
                numDroppedFromSuccess = self.num_dropped_from_success
                numDroppedFromPrimaryFailure = self.num_dropped_from_primary_failure
                numFailedOver = self.num_failed_over
                total = numProcessed + numDroppedFromSuccess + numDroppedFromPrimaryFailure + numFailedOver

                if total == 0:
                    percentageDroppedFromSuccess = 0
                    percentageDroppedFromPrimaryFailure = 0
                    percentageFailedOver = 0
                    percentageSuccess = 0
                else:
                    percentageDroppedFromSuccess = float(numDroppedFromSuccess) / float(total) * 100.0
                    percentageDroppedFromPrimaryFailure = float(numDroppedFromPrimaryFailure) / float(total) * 100.0
                    percentageFailedOver = float(numFailedOver) / float(total) * 100.0
                    percentageSuccess = float(numProcessed) / float(total) * 100.0

                outputQueueSize = self.success_output_queue.qsize()
                failOverOutputQueueSize = self.primary_failure_output_queue.qsize()

                geocodeDataInMemoryCacheSize = getGeocodeDataInMemoryCacheSize()
                geocodeQueryInMemoryCacheSize = getGeocodeQueryInMemoryCacheSize()

                self.num_dropped_from_success = 0
                self.num_dropped_from_primary_failure = 0
                self.num_processed = 0
                self.num_failed_over = 0

                # FEGQ = follower extractor gate queue
                logger.info('Geocoded %d items (%.2f%%), failed over %d items (%.2f%%), dropped successful geocode items %d items (%.2f%%), dropped failed geocode items %d items (%.2f%%) - success output queue size: %d, fail over output queue size: %d - geocode cache size: %d, place cache size %d' % (numProcessed, percentageSuccess, numFailedOver, percentageFailedOver, numDroppedFromSuccess, percentageDroppedFromSuccess, numDroppedFromPrimaryFailure, percentageDroppedFromPrimaryFailure, outputQueueSize, failOverOutputQueueSize, geocodeDataInMemoryCacheSize, geocodeQueryInMemoryCacheSize))

            if success:
                if self.success_output_queue.qsize() < Configuration.ANALYSIS_INPUT_THREAD_SIZE_CAP:
                    self.num_processed += 1
                    self.success_output_queue.put(item)
                else:
                    self.num_dropped_from_success += 1
            else:
                # Make sure the queue doesn't get too full, we only geocode once a second.
                # We don't deal with those that followers because that would take too long.
                if self.primary_failure_output_queue.qsize() <= Configuration.GEOCODE_FROM_CACHE_PRIMARY_FAILURE_OUTPUT_QUEUE_SIZE and (user.has_location or user.has_twitter_place):
                    self.num_failed_over += 1
                    self.primary_failure_output_queue.put(item)
                elif self.high_load_failure_output_queue is not None:
                    self.num_dropped_from_primary_failure += 1
                    self.high_load_failure_output_queue.put(item)


class GeocodeFromExternalThread(BaseThread):
    def __init__(self,
                 geocodeConfig,
                 inputQueue=None,
                 successOutputQueue=None,
                 failureOutputQueue=None):
        super(GeocodeFromExternalThread,self).__init__(self.__class__.__name__,
                                                       criticalThread = True)

        assert isinstance(geocodeConfig, UserGeocodeConfig)

        if inputQueue is None:
            inputQueue = QueueEx()
        if successOutputQueue is None:
            successOutputQueue = QueueEx()

        self.input_queue = inputQueue
        self.success_output_queue = successOutputQueue
        self.geocode_config = geocodeConfig
        self.failure_output_queue = failureOutputQueue

    def _run(self):
        for item in self.input_queue:
            user = getUser(item)
            assert user is not None

            if user.is_geocoded or not user.has_location:
                continue

            user.clearGeocode(True)

            if user.is_geocoded:
                success = True
            else:
                success = user.geocodeLocationFromExternal(self.geocode_config)

            if success:
                logger.info('Succeeded in geocoding user with location %s from external' % user.location_text)
                self.success_output_queue.put(item)
            elif self.failure_output_queue is not None:
                self.failure_output_queue.put(item)

            if not success:
                logger.info('Failed in geocoding user with location %s from external' % user.location_text)

class FollowerExtractorGateThread(BaseThread):
    # We have a follower extractor per twitter thread so that we can do more
    # than one user at a time.
    follower_extractor_threads = dict()
    _follower_extractor_threads_lock = RLock()

    def __init__(self, geocodeUserConfig, inputQueue=None, outputQueue=None, dataCollection=None, userAnalysisList=None):
        super(FollowerExtractorGateThread,self).__init__(self.__class__.__name__,
                                                         criticalThread = True)

        if inputQueue is None:
            inputQueue = QueueEx()
        if outputQueue is None:
            outputQueue = QueueEx()

        assert dataCollection is not None
        assert isinstance(dataCollection, DataCollection)
        assert isinstance(geocodeUserConfig, UserGeocodeConfig)

        self.input_queue = inputQueue
        self.output_queue = outputQueue
        self.geocode_user_config = geocodeUserConfig

        # We use the data collection to check for users which already have followers.
        self.data_collection = dataCollection

        self.user_analysis_list = userAnalysisList

        self.num_dropped = 0
        self.num_processed = 0
        self.log_num_dropped_timer = Timer(Configuration.LOG_DROP_AMOUNT_FREQ_MS,False)

    def getExtractorThreadByTwitterSession(self, twitterSession):
        if not twitterSession.is_session_active:
            return None

        extractorThread = criticalSection(FollowerExtractorGateThread._follower_extractor_threads_lock, lambda: FollowerExtractorGateThread.follower_extractor_threads.get(twitterSession,None))
        if extractorThread is not None:
            return extractorThread
        else:
            def onTerminateFunc():
                def doAction():
                    del FollowerExtractorGateThread.follower_extractor_threads[twitterSession]

                criticalSection(FollowerExtractorGateThread._follower_extractor_threads_lock,doAction)

            newThread = FollowerExtractorThread(self.geocode_user_config, outputQueue=self.output_queue, twitterSession=twitterSession, onTerminateFunc=onTerminateFunc, userAnalysisList=self.user_analysis_list)

            def doAction():
                FollowerExtractorGateThread.follower_extractor_threads[twitterSession] = newThread
            criticalSection(FollowerExtractorGateThread._follower_extractor_threads_lock, doAction)

            newThread.start()
            return newThread

    def shouldProcessUser(self, user):
        if user is None:
            return False

        return not self.data_collection.isDeepUserObjectIn(user)


    def addUser(self, user, maxQueueSize=None, restrictInfluenceArea = True):
        assert isinstance(user, User)
        if user.id is None:
            return False

        if not self.shouldProcessUser(user):
            return False

        extractorThread = self.getExtractorThreadByTwitterSession(user.twitter_session)
        if extractorThread is None:
            return False

        extractorThreadQueue = extractorThread.input_queue
        extractorThreadSession = extractorThread.twitter_session

        if maxQueueSize is not None and extractorThreadQueue.qsize() > maxQueueSize:
            return False

        if not user.is_geocoded:
            return False

        if restrictInfluenceArea is True:
            found = False

            locations = list()
            locations.append(user.location_geocode)
            if user.location_geocode.country is not None:
                locations.append(user.location_geocode.country)
            if user.location_geocode.continent is not None:
                locations.append(user.location_geocode.continent)

            influenceSourceGeocodeIds = extractorThreadSession.parent_instance.influence_source_cache_ids
            influenceSourceRectangles = extractorThreadSession.parent_instance.influence_source_rectangles
            if influenceSourceGeocodeIds is not None:
                for geocodeCacheId in influenceSourceGeocodeIds:
                    for userLocation in locations:
                         if userLocation == geocodeCacheId:
                             found = True
                             break

            if (not found) and influenceSourceRectangles is not None:
                for rectangle in influenceSourceRectangles:
                    south = rectangle[0]
                    east = rectangle[1]
                    north = rectangle[2]
                    west = rectangle[3]

                    for userLocation in locations:
                        userCoord = userLocation.coordinate
                        result = south < userCoord[0] < north and \
                                 east < userCoord[1] < west

                        if result is True:
                            found = True
                            break

            if not found:
                return False

        user.queued_for_follower_enrichment = True
        FollowerExtractorGateThread.lastPlace = user.location_geocode.place_id

        extractorThreadQueue.put(user)
        return True

    def _run(self):
        for item in self.input_queue:
            user = getUser(item)
            assert user is not None
            assert isinstance(user, User)

            if self.log_num_dropped_timer.ticked():
                numDropped = self.num_dropped
                numProcessed = self.num_processed
                total = numDropped + numProcessed
                if total == 0:
                    percentageDropped = 0
                else:
                    percentageDropped = float(numDropped) / float(total) * 100.0
                outputQueueSize = self.output_queue.qsize()

                self.num_dropped = 0
                self.num_processed = 0


                # AQ = analysis queue
                logger.info('Processed %d items, dropped %d items (%.2f%%) from AQ (queue size %d)' % (numProcessed, numDropped, percentageDropped, outputQueueSize))

            # Always add tweets, even if we don't extract the followers of the user.
            if isinstance(item, Tweet):
                if self.output_queue.qsize() < Configuration.ANALYSIS_INPUT_THREAD_SIZE_CAP:
                    self.num_processed += 1
                    self.output_queue.put(item)
                else:
                    self.num_dropped += 1

            # Already has followers loaded, maybe this came back from
            # geocoder, so we can put it in our output queue safely.
            if user.is_followers_loaded or user.is_followee:
                # Don't drop follower information, since that is so valuable.
                self.output_queue.put(item)
                continue

            # Make sure the queue doesn't get too full.
            if Configuration.AUTO_ENRICH_FOLLOWER_INFO_ENABLED:
                # Skip users with too few or twoo many followers.
                if (Configuration.FOLLOWER_ENRICHMENT_GATE_THREAD_MINIMUM_FOLLOWERS != 0 and user.num_followers < Configuration.FOLLOWER_ENRICHMENT_GATE_THREAD_MINIMUM_FOLLOWERS) or \
                   (Configuration.FOLLOWER_ENRICHMENT_GATE_THREAD_MAXIMUM_FOLLOWERS != 0 and user.num_followers > Configuration.FOLLOWER_ENRICHMENT_GATE_THREAD_MAXIMUM_FOLLOWERS):
                    continue

                self.addUser(user, Configuration.FOLLOWER_ENRICHMENT_QUEUE_SIZE)

class FollowerExtractorThread(BaseThread):
    def __init__(self, geocodeUserConfig, outputQueue=None, twitterSession=None, onTerminateFunc=None, userAnalysisList=None):
        super(FollowerExtractorThread,self).__init__(self.__class__.__name__ + "_" + str(getUniqueId()),
                                                     onTerminateFunc,
                                                     criticalThread = False)

        if outputQueue is None:
            outputQueue = QueueEx()
        if userAnalysisList is None:
            userAnalysisList = list()

        assert isinstance(twitterSession, TwitterSession)
        assert isinstance(geocodeUserConfig, UserGeocodeConfig)

        def continueRunningCheck():
            return twitterSession.is_session_active

        def notifyPositionFunc(item, position, lastPoppedItem):
            user = getUser(item)
            if user is None:
                return

            assert isinstance(user, User)
            user.follower_enrichment_progress.onQueuePositionChange(user, position, lastPoppedItem)
            self.output_queue.put(user)

        self.input_queue = QueueNotify(continueRunningCheck,2,notifyPositionFunc)
        self.output_queue = outputQueue
        self.twitter_session = twitterSession
        self.user_analysis_list = userAnalysisList
        self.geocode_user_config = geocodeUserConfig

        self.num_followers_processed = 0
        self.num_followers_geocoded = 0
        self.num_followees_processed = 0
        self.log_performance_timer = Timer(60000,False)

    def _onFailure(self,e):
        logger.error('Follower extractor thread has failed for instance %s, shutting down instance' % self.twitter_session.instance_key)
        self.twitter_session.parent_instance.shutdownInstance()
        super(FollowerExtractorThread,self)._onFailure(e)

    def _run(self):
        for item in self.input_queue:
            user = getUser(item)
            assert user is not None

            if user.is_followers_loaded:
                continue

            if user.twitter_session is None:
                logger.error('User reached enrichment thread with no twitter session')
                continue

            instance = user.twitter_session.parent_instance
            instance_key = user.instance_key
            startTime = instance.constructed_at
            temporalCollection = getTemporalInfluenceCollection(instance_key)

            analysis_list = list()
            for item in self.user_analysis_list:
                analysisObj = item(user)
                if analysisObj is not None:
                    assert isinstance(analysisObj, UserAnalysis)
                    analysis_list.append(analysisObj)

            def idsIterationFunc(userId, iteration, totalIterations):
                if not self.twitter_session.is_session_active:
                    return False

                #logger.info('Retrieved ids of user %d/%d' % (iteration, totalIterations))
                self.output_queue.put(user)

                return True

            def addTemporalEntryForCurrentUser(follower):
                timeId = getTimeIdFromTimestamp(startTime, Configuration.TEMPORAL_STEP, getEpochMs())

                userCacheIds = user.location_geocode.all_geocode_results_cache_id
                followerGeocodeResults = follower.location_geocode.all_geocode_results

                for userCacheId in userCacheIds:
                    userPlaceId = GeocodeResultAbstract.getPlaceIdFromCacheId(userCacheId)
                    userProviderId = GeocodeResultAbstract.getProviderIdFromCacheId(userCacheId)

                    for followerGeocodeResult in followerGeocodeResults:
                        followerPlaceId = followerGeocodeResult.place_id
                        followerProviderId = followerGeocodeResult.provider_id
                        followerPlaceType = followerGeocodeResult.place_type

                        instance.addTemporalEntry(temporalCollection, timeId, userProviderId, userPlaceId, followerProviderId, followerPlaceId, followerPlaceType)

            def iterationFunc(userId, iteration, totalIterations, followersFromLastIteration):
                if followersFromLastIteration is not None:
                    for follower in followersFromLastIteration:
                        if not self.twitter_session.is_session_active:
                            return False

                        assert isinstance(follower, User)
                        follower.is_followee = True

                        follower.geocodeLocationFromCache(self.geocode_user_config, False)
                        self.output_queue.put(follower)

                        # Follower is now ready to be analysed.
                        for item in analysis_list:
                            item.onFollower(follower)

                        self.num_followers_processed += 1

                        if user.is_geocoded and follower.is_geocoded:
                            self.num_followers_geocoded += 1
                            addTemporalEntryForCurrentUser(follower)

                self.output_queue.put(user)
                return True


            # Retrieve followers.
            #logger.info('Attempting to retrieve followers for user: %s' % user)
            user.getFollowerIds(idsIterationFunc)
            result = user.getFollowers(iterationFunc)

            for item in analysis_list:
                user.addAnalyser(item)

            user.queued_for_follower_enrichment = False

            if result is None:
                logger.error('Failed to retrieve followers for user: %s - explanation: %s, %s, %s' % (user.last_follower_enrichment_error, user.is_followers_loaded, user.is_follower_ids_loaded, user))
            #else:
                #logger.info('Retrieved %d followers for user %s' % (len(result), user))

            # Push update.
            self.num_followees_processed += 1
            self.output_queue.put(user)

            if self.log_performance_timer.ticked():
                numFolloweesProcessed = self.num_followees_processed
                numFollowersProcessed = self.num_followers_processed
                numFollowersGeocoded = self.num_followers_geocoded
                self.num_followees_processed = 0
                self.num_followers_processed = 0
                self.num_followers_geocoded = 0

                logger.info('Num followees processed %d, num followers processed %d, num followers geocoded %d' % (numFolloweesProcessed, numFollowersProcessed, numFollowersGeocoded))


        # Prevent this thread from being restarted.
        self.stop()


class AnalysisThread(BaseThread):
    def __init__(self, data, inputQueue=None):
        super(AnalysisThread,self).__init__(self.__class__.__name__,
                                            criticalThread = True)

        if inputQueue is None:
            inputQueue = QueueEx()

        assert isinstance(data, DataCollection)
        self.input_queue = inputQueue
        self.data = data

    def _run(self):
        for item in self.input_queue:
            if isinstance(item, Tweet):
                if item.has_user and item.user.is_geocoded:
                    self.data.addTweet(item)
                    self.data.prune()
                else:
                    self.data.addFailGeocodeTweet(item)
            else:
                if isinstance(item,User):
                    # This will be a user with follower or followee information
                    # so we do want to update the existing record in the database.
                    self.data.addUser(item, True)

class DisplayThread(BaseThread):
    def __init__(self, display):
        super(DisplayThread, self).__init__(self.__class__.__name__,
                                            criticalThread = True)

        self.display = display

    def _run(self):
        while True:
            time.sleep(0.001)
            for item in self.display:
                item.processCachedSignals()



def startThreads(data, display, userAnalysers):
    tweetQueue = QueueEx()

    userGeocodeConfig = UserGeocodeConfig(Configuration.GEOCODE_EXTERNAL_PROVIDER)

    feb = FollowerExtractorGateThread(userGeocodeConfig, dataCollection=data, userAnalysisList=userAnalysers)

    an = AnalysisThread(inputQueue=feb.output_queue, data=data)

    ge = GeocodeFromExternalThread(geocodeConfig=userGeocodeConfig, failureOutputQueue=an.input_queue, successOutputQueue=feb.input_queue)
    di = DisplayThread(display=display)

    gc = GeocodeFromCacheThread(geocodeConfig=userGeocodeConfig, primaryFailureOutputQueue=ge.input_queue, highLoadFailureOutputQueue=an.input_queue, successOutputQueue=feb.input_queue, inMemoryOnly=False)

    gcm = GeocodeFromCacheThread(geocodeConfig=userGeocodeConfig, inputQueue=tweetQueue, primaryFailureOutputQueue=gc.input_queue, highLoadFailureOutputQueue=an.input_queue, successOutputQueue=feb.input_queue, inMemoryOnly=True)

    for n in range(1, Configuration.NUM_GEOCODE_FROM_CACHE_WORKERS_MEMORY_ONLY):
        aux = GeocodeFromCacheThread(geocodeConfig=gcm.geocode_config, inputQueue=gcm.input_queue, primaryFailureOutputQueue=gcm.primary_failure_output_queue, highLoadFailureOutputQueue=gcm.high_load_failure_output_queue, successOutputQueue=gcm.success_output_queue, inMemoryOnly=gcm.in_memory_only)
        aux.start()

    for n in range(1,Configuration.NUM_GEOCODE_FROM_CACHE_WORKERS):
        aux = GeocodeFromCacheThread(geocodeConfig=gc.geocode_config, inputQueue=gc.input_queue, primaryFailureOutputQueue=gc.primary_failure_output_queue, highLoadFailureOutputQueue=gc.high_load_failure_output_queue, successOutputQueue=gc.success_output_queue, inMemoryOnly=gc.in_memory_only)
        aux.start()

    for n in range(1,Configuration.NUM_ANALYSIS_WORKERS):
        aux = AnalysisThread(inputQueue=an.input_queue, data=data)
        aux.start()

        aux = FollowerExtractorGateThread(inputQueue = feb.input_queue, outputQueue = feb.output_queue, geocodeUserConfig=feb.geocode_user_config, dataCollection=feb.data_collection, userAnalysisList=feb.user_analysis_list)
        aux.start()

    gc.start()
    gcm.start()
    ge.start()
    an.start()
    feb.start()
    di.start()

    return {'tweet_queue' : tweetQueue,'follower_extractor_gate_thread' : feb}


def startTwitterThread(twitterInstance,
                       initialData=None):
    #assert isinstance(twitterInstance, TwitterInstance)

    tw = TwitterSession(twitterInstance.twitter_authentication, twitterInstance)
    feed = tw.follow(keywords=twitterInstance.keywords, locations=twitterInstance.geographical_filter_rectangles, feedId=twitterInstance.instance_key)
    twt = TwitterThread(feed=feed, outputQueue=twitterInstance.parent_twitter_instances.tweet_provider, initialData=initialData)
    twt.start()
    return twt