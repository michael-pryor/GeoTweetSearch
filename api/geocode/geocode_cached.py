import logging
from pymongo.database import Database
from api.caching.caching_shared import getDatabase
from api.config import Configuration
from api.geocode.geocode_external import geocodeFromExternal
from api.geocode.geocode_shared import processGeocodeResults, GeocodeResultAbstract, buildGeocodeResult, isIntendedForDirectUse, getGeocodeSearchNamePath
from api.core.utility import join, prepareLowerAlpha, extractWords, callAllCombinations, OrderedDictEx
import re

logger = logging.getLogger(__name__)

def geocodeFromCache(query, providerId, countryCode=None, acceptableTypes=None, biasCoord=None, inMemoryOnly=None):
    query = prepareLowerAlpha(query)
    queries = extractWords(query)

    def func(query):
        query = ' '.join(query)

        results = _geocodeFromCache(query, providerId, countryCode, acceptableTypes, inMemoryOnly, False)
        if results is not None:
            result = processGeocodeResults(results, biasCoord)

            stop = StopIteration()
            stop.my_result = result
            raise stop

    try:
        callAllCombinations(queries,4,func)
    except StopIteration as e:
        return e.my_result
    else:
        return None

inMemoryCacheGeocodeData = OrderedDictEx(True, Configuration.GEOCODE_IN_MEMORY_CACHE_SIZE, True)
def geocodeFromCacheById(cacheId, inMemoryOnly=None):
    if inMemoryOnly is None:
        inMemoryOnly = False

    if 'importance_rating' in cacheId:
        importanceRating = cacheId['importance_rating']
        cacheId = dict(cacheId) # don't modify what was passed in.
        del cacheId['importance_rating'] # remove so doesn't conflict with mongoDB query.
    else:
        importanceRating = None

    if isinstance(cacheId, list):
        success = False
        for item in cacheId:
            if isIntendedForDirectUse(GeocodeResultAbstract.getProviderIdFromCacheId(item)):
                cacheId = item
                success = True
                break

        if not success:
            logger.error('Could not find useful ID from ID list %s' % (unicode(cacheId)))
            return None

    if isIntendedForDirectUse(GeocodeResultAbstract.getProviderIdFromCacheId(cacheId)):
        tup = GeocodeResultAbstract.buildTupleFromCacheId(cacheId)
        returnVal = inMemoryCacheGeocodeData.get(tup,None)

        if returnVal is None:
            if not inMemoryOnly:
                db = getDatabase()
                assert isinstance(db, Database)
                result = db.place.find_one({'_id' : cacheId})
                if result is None:
                    logger.warn('Could not find place cache ID in database: %s' % unicode(cacheId))
                    return None
            else:
                return None

            returnVal = buildGeocodeResult(result['place_data'], cacheId['providerId'], importanceRating)

        # Always update, this will move the item to the back of the ordered dict
        # meaning we have a 'least recently used' cache.
        if returnVal is not None:
            inMemoryCacheGeocodeData[tup] = returnVal

        return returnVal
    else:
        geocode = GeocodeResultAbstract.getGnsByPlaceId(GeocodeResultAbstract.getPlaceIdFromCacheId(cacheId))
        if geocode is None:
            logger.error('Failed to retrieve GNS data with cache ID: %s' % unicode(cacheId))

        return geocode

def getGeocodeDataInMemoryCacheSize():
    return len(inMemoryCacheGeocodeData)


inMemoryCacheGeocodeQuery = OrderedDictEx(True, Configuration.GEOCODE_QUERY_IN_MEMORY_CACHE_SIZE, True)
def _geocodeFromCache(query, providerId, countryCode=None, acceptableTypes=None, inMemoryOnly=None, allowPartial=None):
    if inMemoryOnly is None:
        inMemoryOnly = False
    if allowPartial is None:
        allowPartial = False

    geocodeId = buildKey(query, countryCode, acceptableTypes)

    memoryLookupKey = (geocodeId, countryCode, providerId)
    queryMapping = inMemoryCacheGeocodeQuery.get(memoryLookupKey)

    if queryMapping is None:
        if not inMemoryOnly:
            db = getDatabase()
            queryMapping = db.geocode.find_one({'_id': geocodeId, 'place.providerId' : providerId})
            if queryMapping is None:
                return None
            inMemoryCacheGeocodeQuery[memoryLookupKey] = queryMapping
        else:
            return None

    assert geocodeId == queryMapping['_id']
    placeIdList = queryMapping['place']

    geocodeResults = []
    for placeId in placeIdList:
        place = geocodeFromCacheById(placeId, inMemoryOnly)
        if place is not None:
            geocodeResults.append(place)
        else:
            # Don't return partial result if not in memory, but strictly,
            # we cannot goto database, even if 1 out of 100 records requires it.
            if inMemoryOnly and not allowPartial:
                return None

    if len(geocodeResults) < 0:
        return None

    return geocodeResults

def getGeocodeQueryInMemoryCacheSize():
    return len(inMemoryCacheGeocodeQuery)


def buildKeyFromList(theList):
    theList = sorted(theList)

    return join('_',[prepareLowerAlpha(x) for x in theList])

def buildKey(query, countryCode, acceptableTypes):
    if acceptableTypes is None:
        acceptableTypes = ['None']

    if countryCode is None:
        countryCode = 'None'

    return buildKeyFromList([query, countryCode] + list(acceptableTypes))

def writeGeocodeResultToCache(query, countryCode, acceptableTypes, results):
    db = getDatabase()
    assert(isinstance(db, Database))

    placeIdList = []
    for result in results:
        assert(isinstance(result,GeocodeResultAbstract))
        cacheId = result.cache_id

        cacheIdForPlaceList = cacheId
        if result.has_importance_rating:
            cacheIdForPlaceList = dict(cacheIdForPlaceList)
            cacheIdForPlaceList['importance_rating'] = result.importance_rating

        placeIdList.append(cacheIdForPlaceList)

        # probably should make result.geocodeData part of GeocodeResultAbstract.
        db.place.update({'_id': cacheId}, {'_id' : cacheId, 'place_data': result.geocodeData}, upsert=True)

    geocodeId = buildKey(query, countryCode, acceptableTypes)
    db.geocode.update({'_id': geocodeId}, {'_id' : geocodeId, 'place': placeIdList}, upsert=True)


def geocodeFromExternalAndWriteToCache(query, providerId, countryCode=None, acceptableTypes=None, biasCoord=None, retry=2):
    results = geocodeFromExternal(query, providerId, countryCode, acceptableTypes, retry)
    if results is not None:
        writeGeocodeResultToCache(query, countryCode, acceptableTypes, results)
        return processGeocodeResults(results, biasCoord)
    else:
        return None


def geocodeSearch(providerId, placeName, maxResults = 10):
    db = getDatabase()
    assert isinstance(db, Database)

    logger.info('Searching for location: %s' % placeName)

    regularExpression = re.compile('%s' % placeName,re.IGNORECASE)
    mongoPath = '.'.join(['place_data'] + getGeocodeSearchNamePath(providerId))
    search = {'_id.providerId' : providerId, mongoPath : regularExpression}
    cursor = db.place.find(search)

    results = list()
    count = 0
    for item in cursor:
        result = buildGeocodeResult(item['place_data'],providerId)
        if result is not None:
            results.append(result)
            count += 1
            if count > maxResults:
                break

    return results
