""" The system used here of caching in a dict providerId -> placeId -> count rather than a list of tuples (or lists which behave like tuples in MongoDB)
    was chosen because it means we can do fast lookups when merging data. If we have a list of tuples we need to iterate over both
    the source and destination in full with every merge so writes would become very expensive. However, this has the drawback
    that on reading it is more expensive to order the data by count since we first have to convert it into a list. """
import logging
import time
from api.caching.caching_shared import getCollection, getDatabase, _initializeUsePower2
from api.config import Configuration
from api.core.utility import getEpochMs, upperPowerTwo, Timer
__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

# By only using indexes that we need we save computation and speed up the database.
# Index one is for precise while index two is for inprecise.
indexOneEnabled = True
indexTwoEnabled = False

def _initCollection(collectionName):
    logger.info('Initializing collection: %s' % collectionName)
    _initializeUsePower2(collectionName)

initializedTemporalInfluenceCollections = set()

def getTemporalInfluenceCollection(instanceId):
    global initializedTemporalInfluenceCollections

    collectionName = 'influence_%s' % unicode(instanceId)
    r = getCollection(collectionName)

    if collectionName not in initializedTemporalInfluenceCollections:
        _initCollection(collectionName)
        initializedTemporalInfluenceCollections.add(collectionName)

    return r

def isTemporalInfluenceCollection(collectionName):
    return collectionName.startswith('influence_')

def getTimeIdFromTimestamp(baseTimestamp, baseStep, timestamp):
    if timestamp < baseTimestamp:
        return 0

    timeRange = timestamp - baseTimestamp
    return int(timeRange / baseStep) + 1

def addTemporalEntry(collection, lastTimeId, timeId, source, destination, destinationProviderId):
    global sourceTimeCache

    if lastTimeId is not None and lastTimeId != timeId:
        branchTemporalEntryForwards(collection, lastTimeId, 1, source, None, timeId)

    # Update current record.
    update = {destinationProviderId : {destination : 1}}
    leafTemporalEntry(collection, timeId, 1, source, update, True)

def getTemporalRange(collection, timeIdStart, timeIdEnd, source, combineWith=None, preciseFromBack=True, preciseFromFront=True):
    if timeIdEnd < timeIdStart:
        timeIdEnd = timeIdStart

    timeRange = timeIdEnd - timeIdStart

    # This speeds things up by allowing us to over estimate. We avoid
    # going through smaller nodes to calculate the precise value.
    if not preciseFromBack:
        timeRange = upperPowerTwo(timeRange)

    value = getTemporalEntryLongestLength(collection, timeIdStart, timeIdEnd, source, timeRange, preciseFromFront)
    if value is None:
        return None

    currentTimeLength = value['_id']['length']
    currentTime = value['_id']['time']

    if combineWith is None:
        combineWith = dict()

    mergeCacheData(value['destination'], combineWith)

    nextTime = currentTime - currentTimeLength
    if timeIdEnd > nextTime > timeIdStart:
        getTemporalRange(collection, timeIdStart, nextTime, source, combineWith, preciseFromBack, preciseFromFront)

    return combineWith


def getTemporalEntry(collection, time, length, source):
    result =  collection.find_one({'_id' : {'time' : time,
                                            'length' : length,
                                            'source' : source}})
    logger.debug('Attempting to read temporal data T:%s , L:%s , S:%s: %s' % (time, length, source, unicode(result)))
    return result

def getTemporalEntryLongestLength(collection, timeStart, timeEnd, source, maxLength=None, preciseFromFront=True):
    global indexOneEnabled
    global indexTwoEnabled

    findDic = {'_id.source' : source}

    if maxLength is not None:
        findDic.update({'_id.time' : {'$gte' : timeStart, '$lte' : timeEnd},
                        '_id.length' : {'$lte' : maxLength}})

    # When dealing with tweets closest to the max length.
    # If precise, then we prioritise time over length.
    # If imprecise, then we will prioritise the larger length but may get a less accurate time.
    if preciseFromFront:
        assert indexOneEnabled # need to maintain optimum performance
        result =  collection.find(findDic).sort([('_id.time',-1),('_id.length',-1)]).limit(1)
    else:
        assert indexTwoEnabled # need to maintain optimum performance
        result =  collection.find(findDic).sort([('_id.length',-1),('_id.time',-1)]).limit(1)

    if Configuration.MONGO_EXPLAINS_ENABLED:
        logger.critical('Influence Explain: %s' % unicode(result.explain()))

    returnMe = None
    for item in result:
        returnMe = item
        break

    if returnMe is None:
        resultStr = 'None'
    else:
        resultStr = '(T: %s, L: %s)' % (returnMe['_id']['time'], returnMe['_id']['length'])

    logger.info('Attempting to read temporal data TS:%d, TE:%d, L: (longest, max %s), S:%s: %s' % (timeStart, timeEnd, maxLength, source, resultStr))
    return returnMe

def leafTemporalEntry(collection, time, length, source, destinationsInc, increment):
    global indexOneEnabled
    global indexTwoEnabled

    if indexOneEnabled:
        collection.ensure_index([('_id.source',1),('_id.time',-1),('_id.length',-1)])

    if indexTwoEnabled:
        collection.ensure_index([('_id.source',1),('_id.length',-1),('_id.time',-1)])

    cacheId = {'_id' : {'time' : time,
                        'length' : length,
                        'source' : source}}

    if destinationsInc is not None:
        incDic = dict()
        for providerId, providerIdData in destinationsInc.iteritems():
            for destination, incBy in providerIdData.iteritems():
                incDic['destination.%s.%s' % (providerId,unicode(destination))] = incBy

        if increment:
            cacheUpdate = {'$inc' : incDic}
        else:
            cacheUpdate = {'$set' : incDic}

        collection.update(cacheId, cacheUpdate, upsert=True)

def mergeCacheData(mergeSource, mergeDestination):
    for level1, dataLevel1 in mergeSource.iteritems():
        destinationIncData = mergeDestination.setdefault(level1,dict())
        for level2, incBy in dataLevel1.iteritems():
            mergeItem = destinationIncData.setdefault(level2,0)
            mergeItem += incBy
            destinationIncData[level2] = mergeItem

def branchTemporalEntryForwards(collection, time, length, source, destinationsInc, endTimeLimit):
    if time >= endTimeLimit:
        return

    # Merge with previous time.
    # So if our length is 4, we go back in time 4 time steps and merge with that
    # to create an entry with length 8.
    mergedLength = length * 2

    # Tricky logic to ensure we read and store in the correct slot.
    if (time / length) % 2 != 0:
        mergeWithTime = time + length
        storeMergeResultIn = mergeWithTime
    else:
        mergeWithTime = time - length
        storeMergeResultIn = time

    #logger.info('Merging %d with %d, storing in %d' % (time, mergeWithTime, storeMergeResultIn))

    if mergeWithTime < endTimeLimit:
        # This is the base data.
        # We are making $inc calls to mongodb so we don't need to load
        # the data we're going to merge with. If there is any there it
        # will be merged automatically.
        if destinationsInc is None:
            destinationsInc = getTemporalEntry(collection, time, length, source)
            if destinationsInc is not None:
                destinationsInc = destinationsInc.get('destination', None)
                if destinationsInc is None:
                    destinationsInc = dict()
            else:
                destinationsInc = dict()

        # This is the merge data.
        mergeEntry = getTemporalEntry(collection, mergeWithTime, length, source)
        if mergeEntry is None:
            mergeEntry = dict()
        else:
            mergeEntry = mergeEntry.get('destination', None)
            if mergeEntry is None:
                mergeEntry = dict()


        # Do the merging.
        mergeCacheData(mergeEntry, destinationsInc)

        # Create the new merged leaf.
        leafTemporalEntry(collection, storeMergeResultIn, mergedLength, source, destinationsInc, False)

        # Recurse, in case there is more merging to be done.
        branchTemporalEntryForwards(collection, storeMergeResultIn, mergedLength, source, destinationsInc, endTimeLimit)