import logging
import unittest
from api.config import Configuration
from api.twitter.feed import User, UserAnalysis, Tweet

__author__ = 'Michael Pryor'


logger = logging.getLogger(__name__)

def escapeCsvCell(cell):
    cell = unicode(cell)
    cell = cell.replace('"','""')
    return '"' + cell + '"'

def appendCsvRow(data, cellsList):
    cells = ''
    for cell in cellsList:
        cells += escapeCsvCell(cell) + ','
    cells = cells[:-1]

    if len(data) == 0:
        return cells
    else:
        return data + '\r\n' + cells

def getUserRepresentation(user, outputType):
    assert isinstance(user, User)

    analysisResults = []
    if user.has_analysers:
        for analyser in user.analysers.itervalues():
            assert isinstance(analyser, UserAnalysis)
            analysisResults.append(unicode(analyser.results_viewable))

    analysisResults = appendCsvRow('',analysisResults)

    if user.is_geocoded:
        geocodeCityId = unicode(user.location_geocode.cache_id)
        geocodeCityName = unicode(user.location_geocode.display_name)

        if user.location_geocode.has_country:
            geocodeCountryId = unicode(user.location_geocode.country.cache_id)
            geocodeCountryName = unicode(user.location_geocode.country.display_name)
        else:
            geocodeCountryId = Configuration.CSV_EMPTY_VAL
            geocodeCountryName = Configuration.CSV_EMPTY_VAL

        if user.location_geocode.has_continent:
            geocodeContinentId = unicode(user.location_geocode.continent.cache_id)
            geocodeContinentName = unicode(user.location_geocode.continent.display_name)
        else:
            geocodeContinentId = Configuration.CSV_EMPTY_VAL
            geocodeContinentName = Configuration.CSV_EMPTY_VAL
    else:
        geocodeCityId = Configuration.CSV_EMPTY_VAL
        geocodeCityName = Configuration.CSV_EMPTY_VAL

        geocodeCountryId = Configuration.CSV_EMPTY_VAL
        geocodeCountryName = Configuration.CSV_EMPTY_VAL

        geocodeContinentId = Configuration.CSV_EMPTY_VAL
        geocodeContinentName = Configuration.CSV_EMPTY_VAL

    if user.has_twitter_place:
        twitterPlaceData = user.twitter_place.data
    else:
        twitterPlaceData = Configuration.CSV_EMPTY_VAL

    if user.has_location:
        userLocation = user.location_text
    else:
        userLocation = Configuration.CSV_EMPTY_VAL

    isGeocoded = user.is_geocoded

    if outputType == 2:
        followerInfo = [user.follower_ids_string,
                        user.followee_ids_string,
                        analysisResults]
    elif outputType == 1:
        followerInfo = []
    elif outputType == 3:
        followerInfo = [analysisResults]
    else:
        logger.error('Invalid output type while writing contents: %s' % outputType)
        raise NotImplementedError()


    data =  appendCsvRow('',
                        [ user.id,
                          user.timestamp,
                          unicode(user.data),
                          isGeocoded,
                          userLocation,
                          twitterPlaceData,
                          geocodeCityId,
                          geocodeCityName,
                          geocodeCountryId,
                          geocodeCountryName,
                          geocodeContinentId,
                          geocodeContinentName,
                          user.geocode_bias] + followerInfo)

    return data

def getUserHeader(outputType):
    if outputType == 2:
        followerInfo =  ['follower ids',
                         'followee ids',
                         'user analysis']
    elif outputType == 1:
        followerInfo = []
    elif outputType == 3:
        followerInfo = ['user analysis']
    else:
        logger.error('Invalid output type while writing header: %s' % outputType)
        raise NotImplementedError()

    return appendCsvRow('',
            ['id',
            'timestamp',
            'json',
            'is geocoded',
            'user provided location',
            'twitter place data',
            'geocode location city id',
            'geocode location city name',
            'geocode location country id',
            'geocode location country name',
            'geocode location continent id',
            'geocode location continent name',
            'geocode location bias'] + followerInfo)

def getTweetHeader():
    return appendCsvRow('',
                        ['id',
                         'timestamp',
                         'user id',
                         'json'])

def getTweetRepresentation(tweet):
    assert isinstance(tweet, Tweet)

    userId = Configuration.CSV_EMPTY_VAL
    if tweet.has_user:
        userId = tweet.user.id

    return  appendCsvRow('',
                         [ tweet.id,
                           tweet.timestamp,
                           userId,
                           unicode(tweet.data) ])

class testUtility(unittest.TestCase):
    def testCsv(self):
        result = ''

        result = appendCsvRow(result,['hello','this is "the" world'])
        result = appendCsvRow(result,['what,1\n2','time','is','it?'])

        logger.info(result)
        assert False