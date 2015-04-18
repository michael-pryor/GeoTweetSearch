from abc import ABCMeta, abstractproperty
import copy
import logging
from threading import Lock
import pymongo
from pymongo.database import Database
from pymongo.errors import AutoReconnect
from api.caching.caching_shared import getDatabase, getCollection, _initializeUsePower2
from api.config import Configuration
from api.core.utility import getEpochMs, Timer
from api.geocode.geocode_cached import geocodeFromCacheById
from api.twitter.feed import User, Tweet, Place, buildAnalyserFromName

logger = logging.getLogger(__name__)


def _initCollection(collectionName):
    logger.info('Initializing collection: %s' % collectionName)
    _initializeUsePower2(collectionName)

initializedUserCollections = set()
def getUserCollection(instanceId):
    global isUserCollectionInitialized

    collectionName = 'user_%s' % unicode(instanceId)
    r = getCollection(collectionName)

    if collectionName not in initializedUserCollections:
        _initCollection(collectionName)
        initializedUserCollections.add(collectionName)

    return r

initializedTweetCollections = set()
def getTweetCollection(instanceId):
    global isTweetCollectionInitialized

    collectionName = 'tweet_%s' % unicode(instanceId)
    r = getCollection(collectionName)

    if collectionName not in initializedTweetCollections:
        _initCollection(collectionName)
        initializedTweetCollections.add(collectionName)

    return r

def isUserCollection(collectionName):
    return collectionName.startswith('user_')

def isTweetCollection(collectionName):
    return collectionName.startswith('tweet_')


class Projection(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        super(Projection,self).__init__()

    @abstractproperty
    def projection(self):
        return None

    @property
    def do_query(self):
        """ @return true and the query will run as normal,
                    false and the query won't be run and so no results will be returned. """
        return True


class NoQueryProjection(Projection):
    def __init__(self):
        super(NoQueryProjection,self).__init__()

    @property
    def projection(self):
        raise NotImplementedError()

    @property
    def do_query(self):
        return False

class UserDataProjection(Projection):
    def __init__(self, includeFields):
        super(UserDataProjection, self).__init__()

        self._projection = ['id']
        self._projection += includeFields

    @property
    def projection(self):
        return self._projection

class UserProjection(Projection):
    def __init__(self, includeTimestamp,
                       includeData,
                       dataIncludeSpecific,
                       includeGeocode,
                       includeFollowers,
                       followerProjection,
                       includeFollowees,
                       followeeProjection,
                       includeTwitterPlace,
                       includeLastFollowerEnrichmentError,
                       includeFollowerEnrichmentProgress,
                       includeGeocodeBias,
                       includeGeocodeFrom,
                       includeIsAssociatedWithTweetFlag,
                       includeIsFollowersLoadedFlag,
                       includeIsFolloweeFlag,
                       includeQueuedForFollowerEnrichmentFlag,
                       includeAnalysis):
        super(UserProjection,self).__init__()

        if includeFollowers:
            includeIsFollowersLoadedFlag = True

        if dataIncludeSpecific is not None:
            assert isinstance(dataIncludeSpecific,UserDataProjection)
            assert includeData == True

        if includeFollowees:
            includeIsFolloweeFlag = True

        if followerProjection is not None:
            assert isinstance(followerProjection, Projection)

        if followeeProjection is not None:
            assert isinstance(followeeProjection, Projection)

        self.includeFollowers = includeFollowers
        self.follower_projection = followerProjection
        self.followee_projection = followeeProjection

        pr = dict()
        pr['_id'] = True

        if includeTimestamp:
            pr['timestamp'] = True

        if includeData:
            if dataIncludeSpecific is None:
                pr['data'] = True
            else:
                for key in dataIncludeSpecific.projection:
                    prKey = '%s.%s' % ('data', key)
                    pr[prKey] = True

        else:
            pr['data.id'] = True

        if includeGeocode:
            pr['geocode'] = True

        if includeFollowees:
            pr['known_followees'] = True

        if includeTwitterPlace:
            pr['twitter_place'] = True

        if includeLastFollowerEnrichmentError:
            pr['last_follower_enrichment_error'] = True

        if includeFollowerEnrichmentProgress:
            pr['follower_enrichment_progress'] = True

        if includeGeocodeBias:
            pr['geocode_bias'] = True

        if includeGeocodeFrom:
            pr['geocoded_from'] = True

        if includeIsAssociatedWithTweetFlag:
            pr['is_associated_with_tweet'] = True

        if includeIsFollowersLoadedFlag:
            pr['is_followers_loaded'] = True

        if includeIsFolloweeFlag:
            pr['is_followee'] = True

        if includeQueuedForFollowerEnrichmentFlag:
            pr['queued_for_follower_enrichment'] = True

        if includeAnalysis:
            pr['analysis'] = True

        self._projection = pr

    @property
    def projection(self):
        return self._projection

    @classmethod
    def Id(cls, includeData=False, dataProjection=None):
        return cls(False, includeData, dataProjection, False, False, None, False, None, False, False, False, False, False, False, False, False, False, False)

    @classmethod
    def FollowerEnrichmentFlags(cls):
        return cls(False,False,None,False,False,None,False,None,False,False,False,False,False,False,True,False,True, False)

    @classmethod
    def Geocode(cls, includeData=None, dataProjection=None):
        return cls(False, includeData, dataProjection, True, False, None, False, None, False, False, False, False, False, False, False, False, False, False)

    @classmethod
    def IdName(cls):
        return UserProjection.Id(True, UserDataProjection(['name']))

    @classmethod
    def IdNameImage(cls):
        return UserProjection.Id(True, UserDataProjection(['name', 'profile_image_url']))

    @classmethod
    def GeocodeFollowers(cls, includeFolloweeData, followeeDataProjection, includeFollowersData, followersDataProjection):
        geocodeProjection = UserProjection.Geocode(includeFolloweeData, followeeDataProjection)
        return cls(False, includeFollowersData, followersDataProjection, True, geocodeProjection, False, None, False, False, False, False, False, False, False, False, False, True)

    @classmethod
    def ExcludeRecursiveData(cls, dataProjection=None):
        return cls(True, True, dataProjection, True, False, None, False, None, True, True, True, True, True, True, True, True, True, True)

logUserWritePerformanceTimer = Timer(Configuration.LOG_DROP_AMOUNT_FREQ_MS, False)
def writeUserToCache(user, doUpdate):
    assert isinstance(user, User)

    # Used with $set operation.
    setFields = dict()

    # Used $addToSet operation.
    addToSetFields = dict()

    if user.is_followers_loaded:
        setFields.update({'is_followers_loaded' : True})

    if user.is_followee:
        setFields.update({'is_followee' : True})

        followeeIds = [x.id for x in user.known_followees]
        addToSetFields.update({'known_followees' : {'$each' : followeeIds}})

    if user.has_twitter_place:
        setFields.update({'twitter_place' : user.twitter_place.data})

    if user.is_associated_with_tweet:
        setFields.update({'is_associated_with_tweet' : True})

    if user.last_follower_enrichment_error is not None:
        setFields.update({'last_follower_enrichment_error' : user.last_follower_enrichment_error})

    if user.queued_for_follower_enrichment:
        p = user.follower_enrichment_progress

        queue_progress, user_progress, user_id_progress, enrichment_progress_description, queue_waiting_for_user = p.getTuple()
        if queue_waiting_for_user is not None:
            queue_waiting_for_user = queue_waiting_for_user.id

        setFields.update({'queued_for_follower_enrichment' : user.queued_for_follower_enrichment})

        setFields.update({'follower_enrichment_progress' : (queue_progress,
                                                            user_progress,
                                                            user_id_progress,
                                                            enrichment_progress_description,
                                                            queue_waiting_for_user)})
    else:
        # Remove redundant information.
        if user.is_followers_loaded:
            setFields.update({'follower_enrichment_progress' : None})
            setFields.update({'queued_for_follower_enrichment' : False})

    placeId = None
    if user.is_geocoded:
        placeId = user.location_geocode.all_geocode_results_cache_id

        if user.geocode_bias is not None:
            setFields.update({'geocode_bias' : user.geocode_bias})

        if user.geocoded_from is not None:
            setFields.update({'geocoded_from' : user.geocoded_from})

    if user.has_analysers:
        analysis = [{x[0] : x[1].results_cacheable} for x in user.analysers.iteritems()]
        addToSetFields.update({'analysis' : {'$each' : analysis}})

    theQuery = dict()
    if len(setFields) > 0:
        theQuery.update({'$set' : setFields})

    if len(addToSetFields) > 0:
        theQuery.update({'$addToSet' : addToSetFields})


    collection = getUserCollection(user.instance_key)

    timer = getEpochMs()

    # This is for the user page where followers are looked up.
    # Not sure if sparse=True does anything, pymongo docs not clear on how to create sparse index.
    collection.ensure_index([('known_followees', pymongo.ASCENDING)], sparse = True)

    # For short follow information download.
    # Note: Only place ID is used because indexes are expensive on database RAM,
    # and we don't really need to do provider ID too since it is extremely rare
    # that two providers will have the same place ID. Also note I had some trouble
    # getting MongoDB to use an index with provider ID in it (not sure why, but it
    # wouldn't use the index).
    collection.ensure_index([('is_followers_loaded', pymongo.ASCENDING), ('timestamp', pymongo.ASCENDING)], sparse = True)
    collection.ensure_index([('geocode.placeId', pymongo.ASCENDING), ('is_followers_loaded', pymongo.ASCENDING), ('timestamp', pymongo.ASCENDING)], sparse = True)

    ensureIndexTime = getEpochMs() - timer
    timer = getEpochMs()

    _writeItemToCache(getUserCollection, user.id, user.instance_key, user.data, user.isDataNew, user.timestamp, placeId, theQuery, doUpdate)

    writingToDatabaseTime = getEpochMs() - timer

    # This is an optimization, the next time we see this same user object we won't push its data.
    user.isDataNew = False

    global logUserWritePerformanceTimer
    if logUserWritePerformanceTimer.ticked():
        logger.info('Writing user to database took %dms ensuring index, %dms writing to database' % (ensureIndexTime, writingToDatabaseTime))

logTweetWritePerformanceTimer = Timer(Configuration.LOG_DROP_AMOUNT_FREQ_MS, False)
def writeTweetToCache(tweet):
    placeId = None
    if tweet.user.is_geocoded:
        placeId = tweet.user.location_geocode.all_geocode_results_cache_id

    timer = getEpochMs()

    collection = getTweetCollection(tweet.instance_key)

    collection.ensure_index([('timestamp', pymongo.ASCENDING)]) # for cache download where no place is specified.
    collection.ensure_index([('geocode.placeId', pymongo.ASCENDING), ('timestamp', pymongo.ASCENDING)])

    _writeItemToCache(getTweetCollection, None, tweet.instance_key, tweet.data, tweet.isDataNew, tweet.timestamp, placeId)
    tweet.isDataNew = False

    writingToDatabaseTime = getEpochMs() - timer

    global logTweetWritePerformanceTimer
    if logTweetWritePerformanceTimer.ticked():
        logger.info('Writing tweet to database took %dms' % writingToDatabaseTime)


def _writeItemToCache(getCollectionFunc, itemId, instanceId, data, isDataNew, timestamp, placeId, typeSpecificUpdateQuery=None, doUpdate=True):
    assert instanceId is not None
    instanceId = unicode(instanceId)

    collection = getCollectionFunc(instanceId)

    # We always include these keys in our query.
    essentialQuery = {'timestamp' : timestamp}
    if isDataNew:
        essentialQuery['data'] = data
        essentialQuery['geocode'] = placeId

    # First include type specific query.
    updateQuery = dict()
    if typeSpecificUpdateQuery is not None:
        updateQuery.update(typeSpecificUpdateQuery)

    # Append essential query.
    if itemId is not None and doUpdate is True:
        updateQuery.setdefault('$set',{}).update(essentialQuery)

        # Perform update, use upsert so we insert if not already there.
        collection.update({'_id' : itemId}, updateQuery, upsert=True)
    else:
        if typeSpecificUpdateQuery is not None:
            item = typeSpecificUpdateQuery.get('$set',None)
            if item is not None:
                essentialQuery.update(item)

        if itemId is not None:
            essentialQuery.update({'_id' : itemId})

        collection.insert(essentialQuery)


def _readItemFromCache(constructObjectFunc, getCollectionFunc, itemId, instanceId, projection=None):
    query = {'_id' : itemId}

    assert constructObjectFunc is not None
    assert getCollectionFunc is not None
    assert instanceId is not None
    assert itemId is not None

    if projection is not None and projection.do_query is False:
        return None

    collection = getCollectionFunc(instanceId)
    if projection is None:
        data = collection.find_one(query)
    else:
        data = collection.find_one(query, projection.projection)

    return constructObjectFunc(data)

def fixEpochMsRange(epochMsStartRange, epochMsEndRange):
    if epochMsStartRange is not None and epochMsStartRange > getEpochMs():
        logger.warn('Attempt was made to read from cache with a future epoch, this could cause read/write collision: %d' % epochMsStartRange)
        return None

    if (epochMsStartRange is not None and epochMsEndRange is not None) and epochMsEndRange < epochMsStartRange:
        logger.warn('End epoch is less than start epoch - this is invalid')
        return None

    return epochMsStartRange, epochMsEndRange

def cursorItemsFromCache(instanceId, getCollectionFunc, placeId=None, epochMsStartRange=None, epochMsEndRange=None, pageNum=None, pageSize=None, typeSpecificQuery=None, projection=None, sortByTimestamp=None, typeSpecificHint=None):
    if sortByTimestamp is None:
        sortByTimestamp = True

    epochMsStartRange, epochMsEndRange = fixEpochMsRange(epochMsStartRange, epochMsEndRange)

    if epochMsEndRange is None:
        upperBoundTimestamp = getEpochMs()
    else:
        upperBoundTimestamp = epochMsEndRange

    if projection is not None and projection.do_query is False:
        return None

    assert instanceId is not None
    assert getCollectionFunc is not None
    collection = getCollectionFunc(instanceId)

    logFormatting = 'IN:%s, P:%s, ES:%s, EE:%s, PN:%s, PS:%s, T:%s, P:%s' % (instanceId, placeId, epochMsStartRange, epochMsEndRange, pageNum, pageSize, typeSpecificQuery, projection)

    timer = Timer()
    logger.info('Attempting to read items from cache (%d) -- %s' % (timer.__hash__(),logFormatting))

    findDic = dict()

    timestampDic = None
    if epochMsEndRange is not None:
        if timestampDic is None:
            timestampDic = dict()

        timestampDic.update({'$lt' : epochMsEndRange})

    if epochMsStartRange is not None:
        if timestampDic is None:
            timestampDic = dict()

        timestampDic.update({'$gte' : epochMsStartRange})

    if timestampDic is not None:
        findDic.update({'timestamp' : timestampDic})

    if placeId is not None:
        findDic.update({'geocode.placeId' : placeId['placeId'],
                        'geocode.providerId' : placeId['providerId']})

    # MongoDB sometimes gets it wrong, particularly with geocode.placeId.
    if typeSpecificHint is None:
        if timestampDic is not None:
            if placeId is not None:
                hint = [('geocode.placeId', pymongo.ASCENDING), ('timestamp', pymongo.ASCENDING)]
            else:
                hint = [('timestamp', pymongo.ASCENDING)]
        else:
            if placeId is not None:
                hint = [('geocode.placeId', pymongo.ASCENDING)]
            else:
                hint = None
    else:
        hint = typeSpecificHint

    if typeSpecificQuery is not None:
        findDic.update(typeSpecificQuery)

    if projection is None:
        cursor = collection.find(findDic,timeout=False).hint(hint)
    else:
        cursor = collection.find(findDic, projection.projection,timeout=False).hint(hint)

    if sortByTimestamp:
        cursor = cursor.sort([('timestamp', pymongo.ASCENDING)])

    if pageSize is not None and pageNum is not None:
        cursor = cursor.skip(pageSize*pageNum).limit(pageSize)

    # We use this to calculate progress through the cursor,
    # It is more efficient than using cursor.count.
    cursor.upper_bound_timestamp = upperBoundTimestamp

    timeTaken = timer.time_since_constructed
    logger.info('Successfully setup cursor in %dms -- %s' % (timeTaken,logFormatting))

    if Configuration.MONGO_EXPLAINS_ENABLED:
        logger.critical('Tweet/User Explain: %s' % unicode(cursor.explain()))

    return cursor

def getCursorSize(cursor):
    if cursor is None:
        return 0
    else:
        return cursor.upper_bound_timestamp

def getCursorSizeSlow(cursor):
    timer = Timer()

    if cursor is None:
        return 0

    logger.info('Retrieving cursor size...')

    success = False
    attempt = 1
    maxAttempts = 5
    sizeOfCursor = 0
    while not success:
        try:
            sizeOfCursor = cursor.count(True)
            success = True
        except AutoReconnect as e:
            if attempt <= maxAttempts:
                logger.error('Failed to retrieve cursor size, AutoReconnect exception: %s (%d of %d attempts), errors: %s' % (e.message, attempt, maxAttempts, unicode(e.errors)))
                attempt += 1
                cursor.rewind()
            else:
                raise

    logger.info('Successfully retrieved size of cursor: %d in %dms' % (sizeOfCursor,timer.time_since_constructed))

    return sizeOfCursor

def timestampIterationFunc(obj):
    if obj is None:
        return None
    else:
        return obj.timestamp

def processCursor(cursor, constructObjectFunc, onIterationFunc=None, cursorSize=None, getCurrentIterationFunc=None):
    try:
        if cursor is None:
            return None

        timer = Timer()

        results = []

        if getCurrentIterationFunc is None:
            currentIterationCounter = [0]
            def getIterationFunc(obj, currentIterationCounter=currentIterationCounter):
                currentIterationCounter[0] += 1
                return currentIterationCounter[0]

            getCurrentIterationFunc = getIterationFunc

        brokeOut = False
        iteration = 0
        cursorIterationOffset = 0

        endIteration = cursorSize

        isIterationBoundsInitialised = False

        if onIterationFunc is not None:
            onIterationFunc(cursorIterationOffset, endIteration, False, None, 'base')

        for item in cursor:
            currentObject = constructObjectFunc(item)

            if onIterationFunc is not None:
                iteration = getCurrentIterationFunc(currentObject)

                if iteration is None:
                    continue

                if cursorSize is not None:
                    if not isIterationBoundsInitialised:
                        cursorIterationOffset = iteration - 1 # Iterations don't have to be 0 indexed.
                        endIteration = cursorSize - cursorIterationOffset
                        isIterationBoundsInitialised = True

                    if isIterationBoundsInitialised:
                        iteration -= cursorIterationOffset

                #logger.info('S: %d, M: %d, E: %d' % (0, iteration, endIteration))
                #assert 0 <= iteration <= (endIteration + 5)

                result = onIterationFunc(iteration, endIteration, False, currentObject, 'base')
                if result is False:
                    brokeOut = True
                    break
            else:
                # Don't return in results if we have an iteration func.
                # This is important in case we are processing millions of rows
                # (more than we can fit in memory).
                if currentObject is not None:
                    results.append(currentObject)

        # Signal that we're finished.
        if onIterationFunc is not None:
            if not brokeOut:
                iteration = endIteration

            onIterationFunc(iteration, endIteration, True, None, 'base')

        timeTaken2 = timer.time_since_constructed
        logger.info('Successfully processed cursor in %dms' % timeTaken2)

        timeTaken = timer.time_since_constructed
        logger.info('Successfully read %d items from cache (%d) in %dms' % (len(results),timer.__hash__(),timeTaken))

        if len(results) == 0:
            return None
        else:
            return results
    finally:
        if cursor is not None:
            cursor.close()

def _constructUser(instanceId, twitterSession, cacheData, recursive=True, userProjection=None, onIterationFunc=None):
    if cacheData is None:
        return None

    geocodePlaceId = cacheData.get('geocode',None)
    if geocodePlaceId is None:
        geocode = None
    else:
        geocode = geocodeFromCacheById(geocodePlaceId)

    userId = cacheData.get('_id')
    geocode_bias = cacheData.get('geocode_bias',None)
    geocoded_from = cacheData.get('geocoded_from',None)
    is_followers_loaded = cacheData.get('is_followers_loaded',None)
    is_followee = cacheData.get('is_followee',None)
    is_associated_with_tweet = cacheData.get('is_associated_with_tweet',None)
    last_follower_enrichment_error = cacheData.get('last_follower_enrichment_error',None)
    queued_for_follower_enrichment = cacheData.get('queued_for_follower_enrichment',None)

    known_followees_id = cacheData.get('known_followees',None)

    user_data = cacheData.get('data',None)
    num_followers = None
    if user_data is not None:
        num_followers = user_data.get('followers_count',None)

    totalSubUsers = 0
    subUserIndex = [0]

    # First calculate total size.
    if recursive:
        followees_count = 0
        followers_count = 0

        if known_followees_id is not None:
            followees_count = len(known_followees_id)
            totalSubUsers += followees_count

        if is_followers_loaded and num_followers is not None:
            followers_count = num_followers
            totalSubUsers += followers_count

        if followees_count > 0 or followers_count > 0:
            logger.info('User %s has %d followees and %d followers which will be recursed' % (userId, followees_count, followers_count))

    # Process followees.
    if known_followees_id is None:
        known_followees = None
    elif not recursive:
        known_followees = set()
        for followeeId in known_followees_id:
            followee = User.Id(followeeId,twitterSession)
            known_followees.add(followee)
    else:
        known_followees = set()
        followeeProjection = None
        if userProjection is not None:
            followeeProjection = userProjection.followee_projection

        for followeeId in known_followees_id:
            subUserIndex[0] += 1

            followee = readUserFromCache(followeeId, twitterSession, instanceId, recursive=False, userProjection=followeeProjection)
            if followee is not None:
                known_followees.add(followee)
            else:
                logger.error('Followee could not be found in database (followee id: %s)' % followeeId)

            if onIterationFunc is not None:
                if not onIterationFunc(subUserIndex[0], totalSubUsers, False, followee, 'followee'):
                    return

    # Process followers
    followers = None
    followerIds = None
    if is_followers_loaded:
        followerIds = []
        followers = []

        followerProjection = None
        if userProjection is not None:
            followerProjection = userProjection.follower_projection

        if recursive and is_followers_loaded:
            def onFollowerLoadFunc(iteration, total, isFinished, data, iteratorId, subUserIndex=subUserIndex):
                if data is None:
                    return True

                assert isinstance(data, User)
                followerIds.append(data.id)
                followers.append(data)

                if onIterationFunc is not None:
                    if subUserIndex[0] < totalSubUsers:
                        subUserIndex[0] += 1

                    return onIterationFunc(subUserIndex[0], totalSubUsers, isFinished, data, 'follower')
                else:
                    return True

            followersCursor = cursorUsersFromCache(instanceId, pageNum=0, pageSize=200, followeeOfRequirement=userId, userProjection=followerProjection, sortByTimestamp=False)

            assert num_followers is not None
            processCursor(followersCursor, buildConstructUserFromCacheFunc(twitterSession, instanceId, recursive=False, userProjection=followerProjection, onIterationFunc=onFollowerLoadFunc), onFollowerLoadFunc, num_followers, None)

    tup = cacheData.get('follower_enrichment_progress',None)
    if tup is not None:
        queue_progress, user_progress, user_id_progress, enrichment_progress_description, queue_waiting_for_user = tup

        if queue_waiting_for_user is not None:
            queue_waiting_for_user = readUserFromCache(queue_waiting_for_user, twitterSession, instanceId, recursive=False, userProjection=UserProjection.IdName())

        tup = (queue_progress,
               user_progress,
               user_id_progress,
               enrichment_progress_description,
               queue_waiting_for_user)

    place = None
    twitter_place_data = cacheData.get('twitter_place',None)
    if twitter_place_data is not None:
        place = Place.FromCache(twitter_place_data)

    item = User.FromCache(cacheData.get('data',None),
                          twitterSession,
                          cacheData.get('timestamp',None),
                          geocode,
                          tup,
                          geocode_bias,
                          geocoded_from,
                          is_followee,
                          is_associated_with_tweet,
                          last_follower_enrichment_error,
                          known_followees,
                          place,
                          queued_for_follower_enrichment)

    if followers is not None:
        item.loadFollowers(followerIds, followers)

    analysis = cacheData.get('analysis',None)
    if analysis is not None:
        for analysisSub in analysis:
            for analysisName, analysisData in analysisSub.iteritems():
                analyser = buildAnalyserFromName(analysisName)
                analyser.from_cache(analysisData)
                item.addAnalyser(analyser)

    return item

def buildConstructUserFromCacheFunc(twitterSession, instanceId, recursive, userProjection, onIterationFunc=None):
    return lambda(data): _constructUser(instanceId, twitterSession, data, recursive, userProjection, onIterationFunc)

def _constructTweet(instanceId, twitterSession, cacheData, retrieveUserData, userProjection):
    if cacheData is not None:
        geocode = geocodeFromCacheById(cacheData['geocode'])
        item = Tweet.FromCache(cacheData['data'], twitterSession, cacheData['timestamp'], geocode)

        if retrieveUserData:
            item.user = readUserFromCache(item.user.id, twitterSession, instanceId, False, userProjection)

        return item
    else:
        return None

def buildConstructTweetFromCacheFunc(twitterSession, instanceId, retrieveUserData, userProjection):
    return lambda(data): _constructTweet(instanceId, twitterSession, data, retrieveUserData, userProjection)

def readTweetFromCache(tweetId, twitterSession, instanceId, retrieveUserData=False, userProjection=None):
    return _readItemFromCache(buildConstructTweetFromCacheFunc(twitterSession, instanceId, retrieveUserData, userProjection), getTweetCollection, tweetId, instanceId)

def readUserFromCache(userId, twitterSession, instanceId, recursive=True, userProjection=None):
    return _readItemFromCache(buildConstructUserFromCacheFunc(twitterSession, instanceId, recursive, userProjection), getUserCollection, userId, instanceId, projection=userProjection)

def readTweetsFromCache(twitterSession, instanceId, placeId=None, epochMsStartRange=None, epochMsEndRange=None, pageNum=None, pageSize=None, onIterationFunc=None, retrieveUserData=None, userProjection=None):
    cursor = cursorItemsFromCache(instanceId, getTweetCollection, placeId, epochMsStartRange, epochMsEndRange, pageNum, pageSize)
    return processCursor(cursor, buildConstructTweetFromCacheFunc(twitterSession, instanceId, retrieveUserData, userProjection), onIterationFunc, getCursorSize(cursor), timestampIterationFunc)

def cursorUsersFromCache(instanceId, placeId=None, epochMsStartRange=None, epochMsEndRange=None, pageNum=None, pageSize=None, followeeOfRequirement=None, isFollowersLoadedRequirement=None, associatedWithTweetRequirement=None, userProjection=None, sortByTimestamp=None):
    customSearchCriteria = dict()
    if followeeOfRequirement is not None:
        customSearchCriteria.update({'known_followees' : followeeOfRequirement})

    if associatedWithTweetRequirement:
        customSearchCriteria.update({'is_associated_with_tweet' : associatedWithTweetRequirement})

    if isFollowersLoadedRequirement:
        customSearchCriteria.update({'is_followers_loaded' : isFollowersLoadedRequirement})

    usesTimestampField = epochMsStartRange is not None or epochMsEndRange is not None or sortByTimestamp is not None

    hint = list()

    # Hints must match ensure_index during writing.
    if followeeOfRequirement is not None:
        hint.append(('known_followees', pymongo.ASCENDING))
    else:
        if placeId is not None:
            hint.append(('geocode.placeId', pymongo.ASCENDING))

        if isFollowersLoadedRequirement is not None:
            hint.append(('is_followers_loaded', pymongo.ASCENDING))

            if usesTimestampField:
                hint.append(('timestamp', pymongo.ASCENDING))

    return cursorItemsFromCache(instanceId, getUserCollection, placeId, epochMsStartRange, epochMsEndRange, pageNum, pageSize, customSearchCriteria, userProjection, sortByTimestamp, hint)

def readUsersFromCache(twitterSession, instanceId, placeId=None, epochMsStartRange=None, epochMsEndRange=None, pageNum=None, pageSize=None, followeeOfRequirement=None, isFollowersLoadedRequirement=None, associatedWithTweetRequirement=None, recursive=True, userProjection=None, onIterationFunc=None, sortByTimestamp=None):
    lastIteration = [0]
    lastTotal = [0]
    def onCacheIteration(iteration, total, isFinished, data, iteratorId):
        # We want to pass follower and followee data out as we receive it.
        # We would like to update the iteration and total as a fraction but we use
        # a timestamp method rather than a true count for performance reasons.
        # As a result each user takes an unknown amount of space in the total,
        # and so we can't determine how much space each of its followers should take.
        # We just ignore for now but could introduce another progress bar.
        if iteratorId == 'base':
            lastIteration[0] = iteration
            lastTotal[0] = total
        else:
            isFinished = False

        return onIterationFunc(lastIteration[0], lastTotal[0], isFinished, data, iteratorId)


    if onIterationFunc is not None:
        iterationFuncToUse = onCacheIteration
    else:
        iterationFuncToUse = None

    cursor = cursorUsersFromCache(instanceId, placeId, epochMsStartRange, epochMsEndRange, pageNum, pageSize, followeeOfRequirement, isFollowersLoadedRequirement, associatedWithTweetRequirement, userProjection, sortByTimestamp)
    return processCursor(cursor, buildConstructUserFromCacheFunc(twitterSession, instanceId, recursive, userProjection, iterationFuncToUse), iterationFuncToUse, getCursorSize(cursor), timestampIterationFunc)