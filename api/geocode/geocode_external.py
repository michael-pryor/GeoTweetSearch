import unittest
import requests
from api.config import Configuration, GE_MAP_QUEST, GE_GOOGLE
from api.core.utility import Timer
from api.geocode.geocode_shared import GeocodeResult, GeocodeResultGoogle, BadGeocodeException
import logging
import itertools

logger = logging.getLogger(__name__)

__author__ = 'Michael Pryor'

# 1 every two seconds.
# Confirmed with open map quest that 1 per second is okay, but set to every two seconds to be nice.
geocode_from_external_timer_omq    = Timer.rate_limited(60,120*1000)

# 2500 requests per day (24 hours).
# This works out as once every 35 seconds.
geocode_from_external_timer_google = Timer.rate_limited(2500,24*60*60*1000)

def _geocodeFromExternalOMQ(query, countryCode=None, acceptableTypes=None):
    """ Uses open map quest to do a location search, e.g. if query
        is London then information about London city will be returned.

        Note this method restricts itself to 1 call per second."""
    if query is None:
        return None

    geocode_from_external_timer_omq.waitForTick()
    try:
        url = "http://open.mapquestapi.com/nominatim/v1/search"
        params = {
            "format": "json",
            "q": query,
            "addressdetails" : 1,
            "accept-language" : "en"
        }
        if countryCode is not None:
            params.update({'countrycodes' : countryCode})

        resp = requests.get(url, params=params)

        if resp.ok is False or resp.status_code != 200:
            logger.error('Failed to geocode query "%s", reason: %s' % (query, resp.reason))
            return None
        try:
            json = resp.json()
            if json is None or len(json) < 1:
                return None
        except ValueError as e:
            logger.error('Failed to process json data from open map quest: %s, data: %s' % (e.message, resp.text))
            return None

        results = []
        for item in json:
            theItem = GeocodeResult(item)
            if acceptableTypes is None or theItem.place_type in acceptableTypes:
                results.append(theItem)

        if len(results) == 0:
            return None
        else:
            return results
    finally:
        # Make sure we start timing again from the moment we receive result, so we always
        # have a gap even if it takes a while to get response.
        geocode_from_external_timer_omq.resetTimer()

def _geocodeFromExternalGoogle(query, countryCode=None, acceptableTypes=None):
    """ Uses google geocoding API to do a location search. """
    if query is None:
        return None

    geocode_from_external_timer_google.waitForTick()
    try:
        url = 'http://maps.googleapis.com/maps/api/geocode/json'
        params = {
            'address': query,
            'addressdetails' : 1,
            'sensor' : 'false',
            'language' : 'en-GB'
        }
        if countryCode is not None:
            params.update({'ccTLD' : countryCode})

        resp = requests.get(url, params=params)

        if resp.ok is False:
            logger.error('Failed to geocode query "%s", reason: %s' % (query, resp.reason))
            return None

        try:
            json = resp.json()
            if json is None or len(json) < 1:
                return None
        except ValueError as e:
            logger.error('Failed to process json data from google geocoder: %s, data: %s' % (e.message, resp.text))
            return None

        json = json.get('results')
        if json is None or len(json) < 1:
            return None

        results = []
        for item in json:
            theItem = GeocodeResultGoogle(item)
            if acceptableTypes is None or theItem.place_type in acceptableTypes:
                results.append(theItem)

        if len(results) == 0:
            return None
        else:
            return results
    finally:
        # Make sure we start timing again from the moment we receive result, so we always
        # have a gap even if it takes a while to get response.
        geocode_from_external_timer_google.resetTimer()

def geocodeFromExternal(query, providerId, countryCode=None, acceptableTypes=None, retry=2):
    """ Calls _geocodeFromExternalOMQ but catches exception, logs it
        and repeats - sometimes under heavy load the server may take too
        long to respond and we may get exceptions, so retrying can't hurt. """
    for _ in itertools.repeat(None, retry):
        try:
            if providerId == GE_MAP_QUEST:
                results = _geocodeFromExternalOMQ(query, countryCode, acceptableTypes)
            elif providerId == GE_GOOGLE:
                results = _geocodeFromExternalGoogle(query, countryCode, acceptableTypes)
            else:
                logger.error('Invalid geocode external provider: %s' % providerId)
                results = None

            return results
        except BadGeocodeException as e:
            logger.warn('BadGeocodeException while geocoding from external: %s' % e.message)
            return None


class testGeocodeExternal(unittest.TestCase):
    def testLondon(self):
        assert geocodeFromExternal('France', 'FR', ['country']) is not None

    def testInvalidArgument(self):
        assert geocodeFromExternal('this is not a real place', None) is None
