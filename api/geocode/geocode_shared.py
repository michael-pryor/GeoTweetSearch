from abc import ABCMeta, abstractproperty
from collections import Hashable
import csv
import hashlib
import logging
from api.config import Configuration, GE_GEO_NET, GE_MAP_QUEST, GE_GOOGLE
from api.core.data_structures.tree import Tree
from api.core.utility import getDistance, lower_item, searchDictionary, hashStringToInteger32

logger = logging.getLogger(__name__)

class BadGeocodeException(Exception):
    def __init__(self,message):
        super(BadGeocodeException,self).__init__(message)

class GeocodeResultAbstract(Hashable):
    __metaclass__ = ABCMeta

    isGnsDataInitialized = False
    gnsCountryDataByName = dict()
    gnsCountryDataByIsoCode = dict()
    gnsContinentsByName = dict()
    gnsAllByPlaceId = dict()

    @staticmethod
    def getGnsByPlaceId(key):
        return GeocodeResultAbstract.gnsAllByPlaceId.get(key,None)

    # Note: these 'search' methods are inefficient, but since we have only about 250 countries
    # we are okay. If new worlds are populated in the future we might want to optimize this ;)
    # Consider moving into database, for regex query.
    @staticmethod
    def searchCountryByName(searchName, maxResults = None):
        return searchDictionary(searchName, GeocodeResultAbstract.gnsCountryDataByName, maxResults)

    @staticmethod
    def searchContinentByName(searchName, maxResults = None):
        return searchDictionary(searchName, GeocodeResultAbstract.gnsContinentsByName, maxResults)

    @staticmethod
    def searchGnsByName(searchName, maxResults):
        results = GeocodeResultAbstract.searchContinentByName(searchName, maxResults)
        maxResults -= len(results)
        if maxResults > 0:
            results += GeocodeResultAbstract.searchCountryByName(searchName, maxResults)

        return results

    @staticmethod
    def initializeCountryContinentDataFromCsv():
        if GeocodeResultAbstract.isGnsDataInitialized:
            return

        GeocodeResultAbstract.gnsCountryDataByName.clear()
        GeocodeResultAbstract.gnsCountryDataByIsoCode.clear()
        GeocodeResultAbstract.gnsContinentsByName.clear()

        with open(Configuration.CONTINENT_DATA_CSV, 'rb') as continentFile:
            continentCsv = csv.reader(continentFile, delimiter=',')

            for row in continentCsv:
                continentName, centreLon, centreLat, minLon, minLat, maxLon, maxLat,  = row

                if continentName in GeocodeResultAbstract.gnsContinentsByName:
                    logger.error('Duplicate continent name entry found in continent CSV file: %s' % continentName)

                geocode = GeocodeResultGNS(continentName,centreLon,centreLat,GeocodeResultAbstract.PlaceTypes.CONTINENT, None, None, minLon, minLat, maxLon, maxLat)
                GeocodeResultAbstract.gnsContinentsByName[continentName] = geocode
                GeocodeResultAbstract.gnsAllByPlaceId[geocode.place_id] = geocode
                logger.info('Loaded continent: %s with centre coordinate: %s' % (continentName,unicode(geocode.coordinate)))

        with open(Configuration.COUNTRY_DATA_CSV, 'rb') as csvFile:
            theCsv = csv.reader(csvFile, delimiter=',')

            isFirst = True
            for row in theCsv:
                # skip header.
                if isFirst:
                    isFirst = False
                    continue

                country, isoCode, fipsCode, minLon, minLat, maxLon, maxLat, centreLon, centreLat, continentName = row

                if continentName is not None and len(continentName) > 0:
                    continent = GeocodeResultAbstract.gnsContinentsByName.get(continentName,None)
                    if continent is None:
                        logger.error('Continent "%s" of country "%s" not found in continent list' % (continentName, country))
                else:
                    continent = None

                geocode = GeocodeResultGNS(country, centreLon, centreLat, GeocodeResultAbstract.PlaceTypes.COUNTRY, isoCode, fipsCode, minLon, minLat, maxLon, maxLat, continent)
                GeocodeResultAbstract.gnsCountryDataByName[geocode.display_name] = geocode
                GeocodeResultAbstract.gnsAllByPlaceId[geocode.place_id] = geocode

                if geocode.has_iso_code:
                    if geocode.iso_code in GeocodeResultAbstract.gnsCountryDataByIsoCode:
                        logger.error('Duplicate iso code found: "%s" and "%s" share "%s"' % (geocode.display_name,
                                                                                             GeocodeResultAbstract.gnsCountryDataByIsoCode[geocode.iso_code],
                                                                                             geocode.iso_code))

                    GeocodeResultAbstract.gnsCountryDataByIsoCode[geocode.iso_code] = geocode

        GeocodeResultAbstract.isGnsDataInitialized = True


    class PlaceTypes:
        BOROUGH = 4
        CITY = 1
        COUNTRY = 2
        CONTINENT = 3


    @staticmethod
    def buildCacheId(providerId, placeId):
        if providerId is None or placeId is None:
            return None

        return {'providerId' : providerId, 'placeId' : placeId}

    @staticmethod
    def buildCacheIdTuple(providerId, placeId):
        if providerId is None or placeId is None:
            return None

        return providerId, placeId

    @staticmethod
    def buildCacheIdFromTuple(cacheIdTuple):
        providerId, placeId = cacheIdTuple
        return GeocodeResultAbstract.buildCacheId(providerId, placeId)

    @staticmethod
    def buildTupleFromCacheId(cacheId):
        return GeocodeResultAbstract.buildCacheIdTuple(cacheId['providerId'], cacheId['placeId'])

    @staticmethod
    def getProviderIdFromCacheId(cacheId):
        return cacheId['providerId']

    @staticmethod
    def getPlaceIdFromCacheId(cacheId):
        return cacheId['placeId']

    def __init__(self):
        super(GeocodeResultAbstract, self).__init__()

    def __str__(self):
        return self.display_name

    def __unicode__(self):
        return self.display_name

    def __repr__(self):
        return '<GeocodeResult - %s>' % self

    def __int__(self):
        return hash(self)

    def __eq__(self, other):
        try:
            if isinstance(other, GeocodeResultAbstract):
                return hash(self) == hash(other)
            elif isinstance(other, dict):
                placeId = GeocodeResultAbstract.getPlaceIdFromCacheId(other)
                providerId = GeocodeResultAbstract.getProviderIdFromCacheId(other)

                return placeId == self.place_id and providerId == self.provider_id
            elif isinstance(other, int):
                return hash(self) == other
            elif isinstance(other, tuple):
                return self.cache_id_tuple == other
            else:
                return False
        except (AttributeError, TypeError):
            return False


    def __hash__(self):
        return hash(self.cache_id_tuple)

    @abstractproperty
    def provider(self):
        pass

    @abstractproperty
    def provider_id(self):
        pass

    @abstractproperty
    def display_name(self):
        pass

    @abstractproperty
    def cache_id(self):
        pass

    @property
    def cache_id_tuple(self):
        return GeocodeResultAbstract.buildTupleFromCacheId(self.cache_id)

    @abstractproperty
    def place_id(self):
        pass

    @abstractproperty
    def coordinate(self):
        """ @return center coordinate tuple in form: latitude,longitude """
        pass

    @abstractproperty
    def bounding_box_true(self):
        """ @return [south, north, west, east]
            e.g. [u'53.787416687', u'53.8074205017', u'-1.55379415512', u'-1.53379403591'] """
        pass

    @property
    def has_bounding_box(self):
        bb = self.bounding_box_true

        return bb is not None and \
               len(bb) >= 4 and \
               bb[0] is not None and \
               bb[1] is not None and \
               bb[2] is not None and \
               bb[3] is not None

    @property
    def bounding_box(self):
        if not self.has_bounding_box:
            return None

        bb = self.bounding_box_true

        xMult = self.bounding_box_width_multiplier
        yMult = self.bounding_box_height_multiplier

        xNormMiddle = (bb[1] - bb[0]) / 2.0
        yNormMiddle = (bb[3] - bb[2]) / 2.0

        xChange = xNormMiddle * xMult
        yChange = yNormMiddle * yMult

        return [bb[0] - yChange, bb[1] + yChange, bb[2] - xChange, bb[3] + xChange]

    @property
    def bounding_box_height_multiplier(self):
        return self.bounding_box_multiplier

    @property
    def bounding_box_width_multiplier(self):
        return self.bounding_box_multiplier

    @property
    def bounding_box_multiplier(self):
        return 0.0

    @property
    def coordinate_north_east(self):
        """ @return Uses bounding_box, returning north east point in tuple form: latitude,longitude """
        if not self.has_bounding_box:
            return None

        bb = self.bounding_box
        return bb[1], bb[3]

    @property
    def coordinate_north_west(self):
        """ @return Uses bounding_box, returning north west point in tuple form: latitude,longitude """
        if not self.has_bounding_box:
            return None

        bb = self.bounding_box
        return bb[1], bb[2]

    @property
    def coordinate_south_east(self):
        """ @return Uses bounding_box, returning south east point in tuple form: latitude,longitude """
        if not self.has_bounding_box:
            return None

        bb = self.bounding_box
        return bb[0], bb[3]

    @property
    def coordinate_south_west(self):
        """ @return Uses bounding_box, returning south west point in tuple form: latitude,longitude """
        if not self.has_bounding_box:
            return None

        bb = self.bounding_box
        return bb[0], bb[2]

    @abstractproperty
    def place_type(self):
        """ @return type of place e.g. PlaceType.CITY """
        pass

    @abstractproperty
    def country_iso_code(self):
        pass

    @property
    def has_country_iso_code(self):
        return self.country_iso_code is not None

    @property
    def country(self):
        if not self.has_country_iso_code:
            return None

        if not GeocodeResultAbstract.isGnsDataInitialized:
            GeocodeResultAbstract.initializeCountryContinentDataFromCsv()

        # In case initialization failed.
        if not GeocodeResultAbstract.isGnsDataInitialized:
            return

        try:
            return self._country
        except AttributeError:
            self._country = GeocodeResultAbstract.gnsCountryDataByIsoCode.get(self.country_iso_code,None)
            if self._country is None:
                logger.warn('Failed to find country with ISO code: %s when processing location: %s' % (self.country_iso_code, self.display_name))

            return self._country

    @property
    def has_country(self):
        return self.country is not None

    @property
    def has_continent(self):
        return self.has_country and self.country.has_continent

    @property
    def continent(self):
        if not self.has_continent:
            return None

        return self.country.continent

    @property
    def all_geocode_results(self):
        x = [self]
        if self.has_country:
            x.append(self.country)
        if self.has_continent:
            x.append(self.continent)

        return x

    @property
    def all_geocode_results_cache_id(self):
        x = list()

        allResults = self.all_geocode_results
        for result in allResults:
            x.append(result.cache_id)

        return x

    @property
    def has_importance_rating(self):
        return self.importance_rating is not None

    @property
    def importance_rating(self):
        try:
            return self._importance_rating
        except AttributeError:
            return None

    @importance_rating.setter
    def importance_rating(self, value):
        self._importance_rating = value

    @abstractproperty
    def display_name_short(self):
        pass

class GeocodeResultFailed(GeocodeResultAbstract):
    def __init__(self):
        super(GeocodeResultFailed, self).__init__()

    @property
    def provider(self):
        return 'N/A'

    @property
    def provider_id(self):
        raise NotImplementedError()

    @property
    def display_name(self):
        return '[not geocoded]'

    @property
    def display_name_short(self):
        return '[not geocoded]'

    @property
    def cache_id(self):
        raise NotImplementedError()

    @property
    def place_id(self):
        raise NotImplementedError()

    @property
    def coordinate(self):
        raise NotImplementedError()

    @property
    def bounding_box_true(self):
        raise NotImplementedError()

    @property
    def place_type(self):
        raise NotImplementedError()

    @property
    def country_iso_code(self):
        raise NotImplementedError()

    @property
    def importance_rating(self):
        raise NotImplementedError()

class GeocodeResult(GeocodeResultAbstract):
    def __init__(self, geocodeData):
        """ @param geocodeData 1. A dictionary of data to be parsed and represented by this object. """
        super(GeocodeResult, self).__init__()

        self.geocodeData = Tree.make(geocodeData)

        # Need to force country code to be lower as we use it for country lookup.
        def customLowerItem(item):
            if item is None:
                raise BadGeocodeException('Geocode result with no country code, ignoring result: %s (%s)' % (unicode(self.cache_id),unicode(self.display_name)))

            return lower_item(item)

        self.geocodeData.applyFunctionInTree(customLowerItem, ['address','country_code'])

        self._display_name_short = None
        if self.place_type == GeocodeResultAbstract.PlaceTypes.CITY:
            self._display_name_short = self.geocodeData.getFromTree(['address','city'])
        elif self.place_type == GeocodeResultAbstract.PlaceTypes.COUNTRY:
            self._display_name_short = self.geocodeData.getFromTree(['address','country'])

        # As fall back default to full display name.
        if self._display_name_short is None:
            self._display_name_short = self.display_name

    @property
    def provider(self):
        return 'open map quest'

    @property
    def provider_id(self):
        return GE_MAP_QUEST

    @property
    def display_name(self):
        return self.geocodeData.getFromTree(['display_name'])

    @property
    def cache_id(self):
        return GeocodeResultAbstract.buildCacheId(self.provider_id,self.place_id)

    @property
    def place_id(self):
        return int(self.geocodeData.getFromTree(['place_id']))

    @property
    def coordinate(self):
        """ @return center coordinate tuple in form: latitude,longitude """
        if 'lon' not in self.geocodeData or 'lat' not in self.geocodeData:
            return None

        return float(self.geocodeData.get('lat')), float(self.geocodeData.get('lon'))

    @property
    def bounding_box_true(self):
        """ @return [south, north, west, east]
            e.g. [u'53.787416687', u'53.8074205017', u'-1.55379415512', u'-1.53379403591'] """
        bb = self.geocodeData.getFromTree(['boundingbox'])
        return (float(bb[0]),
                float(bb[1]),
                float(bb[2]),
                float(bb[3]))

    @property
    def bounding_box_height_multiplier(self):
        return 0.5

    @property
    def bounding_box_width_multiplier(self):
        return 0.5

    @property
    def place_type(self):
        """ @return type of place e.g. PlaceType.CITY """
        geocodeType = self.geocodeData.getFromTree(['type'])
        if geocodeType == 'city':
            return GeocodeResultAbstract.PlaceTypes.CITY
        # Alot of cities are listed as administrative, and we can take a guess that
        # if city is in its address its possibly a city we want. Hopefully we don't
        # get too much garbage!
        elif geocodeType == 'administrative' and self.geocodeData.getFromTree(['class']) == 'boundary' and self.geocodeData.getFromTree(['address','city']) is not None:
            return GeocodeResultAbstract.PlaceTypes.CITY
        elif geocodeType == 'country':
            return GeocodeResultAbstract.PlaceTypes.COUNTRY
        else:
            return None

    @property
    def country_iso_code(self):
        return self.geocodeData.getFromTree(['address','country_code'])

    @GeocodeResultAbstract.importance_rating.getter
    def importance_rating(self):
        rating = super(GeocodeResult,self).importance_rating
        if rating is not None:
            return rating

        rating = self.geocodeData.getFromTree(['importance'])

        # Not sure what rating is out of but have seen some that are > 1.0
        if rating is not None:
            return rating / 2.0

    @property
    def display_name_short(self):
        return self._display_name_short


class GeocodeResultGoogle(GeocodeResultAbstract):
    def __init__(self, geocodeData):
        super(GeocodeResultGoogle, self).__init__()

        self.geocodeData = Tree.make(geocodeData)

        dName = self.display_name
        if dName is None:
            self._display_name_short = None
        else:
            self._display_name_short = dName.split(',')[0]

    @property
    def provider(self):
        return 'google'

    @property
    def provider_id(self):
        return GE_GOOGLE

    @property
    def display_name(self):
        return self.geocodeData.getFromTree(['formatted_address'])

    @property
    def display_name_short(self):
        return self._display_name_short

    @property
    def cache_id(self):
        return GeocodeResultAbstract.buildCacheId(self.provider_id,self.place_id)

    @property
    def place_id(self):
        return hashStringToInteger32(self.display_name)

    @property
    def coordinate(self):
        """ @return center coordinate tuple in form: latitude,longitude """
        coord = self.geocodeData.getFromTree(['geometry','location'])

        lat = coord.get('lat',None)
        lng = coord.get('lng',None)

        if lat is None or lng is None:
            return None

        return float(lat), float(lng)

    @property
    def bounding_box_true(self):
        """ @return [south, north, west, east]
            e.g. [u'53.787416687', u'53.8074205017', u'-1.55379415512', u'-1.53379403591'] """
        return   (self.geocodeData.getFromTree(['geometry','bounds','southwest','lat']),
                  self.geocodeData.getFromTree(['geometry','bounds','northeast','lat']),
                  self.geocodeData.getFromTree(['geometry','bounds','southwest','lng']),
                  self.geocodeData.getFromTree(['geometry','bounds','northeast','lng']))

    @property
    def bounding_box_height_multiplier(self):
        return 0.5

    @property
    def bounding_box_width_multiplier(self):
        return 1.5

    @property
    def place_type(self):
        """ @return type of place e.g. PlaceType.CITY """
        theTypes = self.geocodeData.getFromTree(['types'])
        if 'locality' in theTypes:
            return GeocodeResultAbstract.PlaceTypes.CITY
        elif 'country' in theTypes:
            return GeocodeResultAbstract.PlaceTypes.COUNTRY
        elif 'administrative_area_level_3' in theTypes or 'administrative_area_level_2' in theTypes:
            return GeocodeResultAbstract.PlaceTypes.BOROUGH
        else:
            return None

    @property
    def country_iso_code(self):
        try:
            return self._country_iso_code
        except AttributeError:
            try:
                addresses = self.geocodeData.getFromTree(['address_components'])
                if addresses is None:
                    raise KeyError('address_components field missing from google geocode result')

                for address in addresses:
                    addressTypes = address['types']
                    if 'country' in addressTypes:
                        self._country_iso_code = address['short_name'].lower()
                        return self._country_iso_code

                self._country_iso_code = None
                return None
            except KeyError as e:
                logger.warn('Badly formed geocode result from google when attempting to parse country ISO code: %s' % e.message)
                self._country_iso_code = None


class GeocodeResultGNS(GeocodeResultAbstract):
    currentHashCode = 0

    def __init__(self,
                 displayName,
                 centreLon,
                 centreLat,
                 placeType,
                 isoCode=None,
                 fipsCode=None,
                 minLon=None,
                 minLat=None,
                 maxLon=None,
                 maxLat=None,
                 continent=None):
        super(GeocodeResultGNS, self).__init__()
        if isoCode is not None:
            isoCode = isoCode.lower()

        if fipsCode is not None:
            fipsCode = fipsCode.lower()

        self._display_name = displayName
        self._coordinate = (centreLat, centreLon)

        if minLat is not None and maxLat is not None and minLon is not None and maxLon is not None:
            self._bounding_box = [float(minLat), float(maxLat), float(minLon), float(maxLon)] # [south, north, west, east]
        else:
            self._bounding_box = None

        self.iso_code = isoCode
        self.fips_code = fipsCode
        if continent is not None:
            assert isinstance(continent, GeocodeResultAbstract)
        self._continent = continent
        self._place_type = placeType

        assert self.place_type is not None

        self._hashCode = GeocodeResultGNS.currentHashCode
        GeocodeResultGNS.currentHashCode += 1

    @property
    def has_iso_code(self):
        return self.iso_code is not None and len(self.iso_code) != 0

    @property
    def has_fips_code(self):
        return self.fips_code is not None

    @property
    def provider(self):
        return 'GEO Net'

    @property
    def provider_id(self):
        return GE_GEO_NET

    @property
    def display_name(self):
        return self._display_name

    @property
    def display_name_short(self):
        return self.display_name

    @property
    def cache_id(self):
        return GeocodeResultAbstract.buildCacheId(self.provider_id,self.place_id)

    @property
    def place_id(self):
        return self._hashCode

    @property
    def coordinate(self):
        return self._coordinate

    @property
    def bounding_box_true(self):
        return self._bounding_box

    @property
    def place_type(self):
        return self._place_type

    @property
    def country_iso_code(self):
        return self.iso_code

    @property
    def has_continent(self):
        return self._continent is not None

    @property
    def continent(self):
        if not self.has_continent:
            return None

        return self._continent

    @property
    def country(self):
        """ Country should not return itself, otherwise when displaying location page,
            we say 'country a is a part of country a' which is true but not very useful. """
        if self.place_type == GeocodeResultAbstract.PlaceTypes.COUNTRY:
            return None
        else:
            return super(GeocodeResultGNS, self).country


def buildGeocodeResult(data, providerId, importanceRating=None):
    try:
        if providerId == GE_MAP_QUEST:
            result = GeocodeResult(data)
        elif providerId == GE_GOOGLE:
            result = GeocodeResultGoogle(data)
        elif providerId == GE_GEO_NET:
            raise NotImplementedError()
        else:
            logger.error('Invalid geocode external provider (buildGeocodeResult): %s' % providerId)
            return None

        if importanceRating is not None:
            result.importance_rating = importanceRating

        if result.place_type is None:
            return None

        return result
    except BadGeocodeException as e:
        logger.warn('BadGeocodeException: %s' % e.message)
        return None

def getGeocodeSearchNamePath(providerId):
    """ Item of data within raw geocode data that is used for searching. """
    if providerId == GE_GOOGLE:
        return ['formatted_address']
    elif providerId == GE_MAP_QUEST:
        return ['display_name']
    else:
        raise NotImplementedError()

def isIntendedForDirectUse(providerId):
    """ GE_GEO_NET data is a small amount of data on countries and continents.
        We store this in memory but store references to it in the database.
        We never store this data in the database and it is used dynamically.
        Users are not expected to construct GE_GEO_NET type objects from the database. """
    if providerId == GE_MAP_QUEST or providerId == GE_GOOGLE:
        return True
    elif providerId == GE_GEO_NET:
        return False
    else:
        logger.error('Invalid geocode external provider (isIntendedForDirectUse): %s' % providerId)
        return None


def processGeocodeResults(results, biasCoord):
    if results is None or len(results) == 0:
        return None

    # Sort results in order with closest to bias first.
    ratings = list()
    if biasCoord is not None:
        ratings = list()
        for result in results:
            assert(isinstance(result, GeocodeResultAbstract))
            rating = getDistance(result.coordinate, biasCoord)

            # If a location is deemed more important, then reduce distance
            # (making the location more desirable).
            if result.has_importance_rating:
                rating *= (1.0 - result.importance_rating)

            ratings.append((result, rating))
    else:
        for result in results:
            if result.has_importance_rating:
                ratings.append((result,  (1.0 - result.importance_rating)))
            else:
                ratings.append((result, 0))

    ratings = sorted(ratings,key=lambda x: x[1])

    results = []
    for item, distance in ratings:
        results.append(item)

    finalResult = results[0]
    assert isinstance(finalResult, GeocodeResultAbstract)
    return finalResult