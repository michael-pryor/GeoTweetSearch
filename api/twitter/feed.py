from abc import ABCMeta, abstractmethod, abstractproperty
from collections import Hashable
import logging
import json
import math
import requests
from requests_oauthlib import OAuth1
from api.config import Configuration
from api.core.data_structures.tree import Tree
from api.core.data_structures.timestamp import Timestamped
from api.geocode.geocode_shared import GeocodeResultAbstract, GeocodeResultFailed
from api.geocode.geocode_cached import geocodeFromCache, geocodeFromExternalAndWriteToCache, geocodeFromCacheById
from ..core.utility import reverse_list, splitList, Timer, getMidPointBox, getEpochMs, getUniqueId

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class TwitterAuthentication:
    def __init__(self, consumer_token, consumer_secret, access_token, access_secret):
        self.consumer_token = consumer_token
        self.consumer_secret = consumer_secret
        self.access_token = access_token
        self.access_secret = access_secret

class TwitterSession(object):
    # If the twitter API changes we will need to update this
    # to ensure progress bars work correctly.
    GET_FOLLOWER_IDS_QUANTITY_PER_TWITTER_CALL = Configuration.TWITTER_USERS_PER_ID_LOOKUP

    class SessionException(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return '%s' % self.value

    def __init__(self, twitterAuthentication, twitterInstance):
        super(TwitterSession, self).__init__()

        #assert isinstance(twitterInstance, TwitterInstance)
        assert isinstance(twitterAuthentication, TwitterAuthentication)

        oauth = OAuth1(twitterAuthentication.consumer_token,
                       client_secret=twitterAuthentication.consumer_secret,
                       resource_owner_key=twitterAuthentication.access_token,
                       resource_owner_secret=twitterAuthentication.access_secret,
                       signature_type='auth_header')

        self._session = requests.session()
        self._session.auth = oauth
        self.twitter_authentication = twitterAuthentication

        if twitterInstance is not None:
            self.instance_key = twitterInstance.instance_key
        else:
            self.instance_key = None
        self.parent_instance = twitterInstance
        self.is_session_active = True

        self.follower_enrichment_timer = Timer.rate_limited(Configuration.TWITTER_USERS_PER_ID_LOOKUP_RATE, Configuration.TWITTER_RATE_LIMIT_WINDOW)
        self.users_from_ids_timer = Timer.rate_limited(Configuration.TWITTER_USERS_PER_USER_LOOKUP_RATE, Configuration.TWITTER_RATE_LIMIT_WINDOW)

        self.statuses_timer = Timer.rate_limited(180, 900000)
        self.status_timer = Timer.rate_limited(180, 900000)

    def close(self):
        # This doesn't close the long running post request we have on twitter streaming API,
        # I couldn't find a way to do this, so we have to wait for next message from
        # twitter streaming API and then close connection.
        self._session.close()
        self.is_session_active = False

    def tweet(self, status):
        self._session.post("https://api.twitter.com/1.1/statuses/update.json", {'status': status})

    def _getFollowerIds(self, userId, cursor, failures=0, isScreenName=False):
        self.follower_enrichment_timer.waitForTick()

        try:
            params = {'cursor' : cursor}
            if isScreenName is False:
                params.update({'user_id' : userId})
            else:
                params.update({'screen_name' : userId})

            result = self._session.get("https://api.twitter.com/1.1/followers/ids.json",
                params=params)
            if not result.ok:
                raise TwitterSession.SessionException('Response contains errors: %s' % result.reason)

            return result
        except (requests.ConnectionError, requests.HTTPError, TwitterSession.SessionException) as e:
            failures += 1

            if failures >= Configuration.MAX_FAILURES_GET_FOLLOWERS:
                logger.error('_getFollowerIds failed %d times: %s' % (failures, e))
                raise TwitterSession.SessionException('Failed to retrieve follower IDs of user %d after %d attempts, reason: %s' % (userId, failures, e))

            logger.warn('_getFollowerIds failed %d times: %s' % (failures, e))
            return self._getFollowerIds(userId, cursor, failures)

    def getFollowerIds(self, userId, funcIteration=None, isScreenName = False):
        cursor = -1
        idList = []

        iteration = 1
        while True:
            if funcIteration is not None:
                if funcIteration(userId, iteration) is False:
                    return idList

            iteration += 1

            queryResult = self._getFollowerIds(userId, cursor, isScreenName=isScreenName)
            json = queryResult.json()
            idList += json['ids']

            cursor = json['next_cursor']

            if cursor == 0:
                if funcIteration is not None:
                    funcIteration(userId, iteration)

                return idList

    def getStatuses(self, screenName, sinceId, count):
        return self._getStatuses(screenName, sinceId, count).json()

    def getStatus(self, statusId):
        return self._getStatus(statusId)

    def _getStatus(self, maxId, failures=0):
        self.status_timer.waitForTick()

        try:
            result = self._session.get('https://api.twitter.com/1.1/statuses/show.json', params={'id' : maxId})
            if not result.ok:
                raise TwitterSession.SessionException('Response contains errors: %s' % result.reason)
            return Tweet(result.json(),self)
        except (requests.ConnectionError, requests.HTTPError, TwitterSession.SessionException) as e:
            failures += 1

            if failures >= Configuration.MAX_FAILURES_ENRICH_USER_INFO:
                raise TwitterSession.SessionException('Failed to retrieve status from ID after %d attempts, reason: %s' % (failures, e))

            logger.warn('_getStatus failed %d times: %s' % (failures, e))
            return self._getStatus(maxId, failures)

    def _getStatuses(self, screenName, maxId, count, failures=0):
        self.users_from_ids_timer.waitForTick()

        try:
            params={'screen_name': screenName, 'count': count}
            if maxId is not None:
                params.update({'max_id': maxId})

            result = self._session.get('https://api.twitter.com/1.1/statuses/user_timeline.json',
                params=params)
            if not result.ok:
                raise TwitterSession.SessionException('Response contains errors: %s' % result.reason)

            return result
        except (requests.ConnectionError, requests.HTTPError, TwitterSession.SessionException) as e:
            failures += 1

            if failures >= Configuration.MAX_FAILURES_ENRICH_USER_INFO:
                raise TwitterSession.SessionException('Failed to retrieve statuses after %d attempts, reason: %s' % (failures, e))

            logger.warn('_getStatuses failed %d times: %s' % (failures, e))
            return self._getStatuses(screenName, maxId, count, failures)

    def _getUsersFromIds(self, userIds, includeEntities, failures=0):
        self.users_from_ids_timer.waitForTick()

        try:
            result = self._session.get('https://api.twitter.com/1.1/users/lookup.json',
                params={'user_id': userIds, 'include_entities': includeEntities})
            if not result.ok:
                raise TwitterSession.SessionException('Response contains errors: %s' % result.reason)

            return result
        except (requests.ConnectionError, requests.HTTPError, TwitterSession.SessionException) as e:
            failures += 1

            if failures >= Configuration.MAX_FAILURES_ENRICH_USER_INFO:
                raise TwitterSession.SessionException('Failed to retrieve user details from IDs after %d attempts, reason: %s' % (failures, e))

            logger.warn('_getUsersFromIds failed %d times: %s' % (failures, e))
            return self._getUsersFromIds(userIds, includeEntities, failures)

    def getUsersFromIds(self, followee, userIds, includeEntities=False, funcIteration=None):
        assert userIds is not None
       # assert isinstance(followee, User)

        userIds = splitList(userIds, Configuration.TWITTER_USERS_PER_USER_LOOKUP)
        results = []
        lastResults = []
        iteration = 1
        numIterations = len(userIds) + 1
        for userIdSet in userIds:
            if funcIteration is not None:
                if funcIteration(iteration, numIterations, lastResults) is False:
                    return results

            iteration += 1

            userIdSet = (str(x) for x in userIdSet)
            userIdStr = ','.join(userIdSet)
            queryResult = self._getUsersFromIds(userIdStr, includeEntities)

            json = queryResult.json()

            lastResults = [User(x, twitterSession=self, knownFollowees=set([followee])) for x in json]
            results += lastResults

        if funcIteration is not None:
            funcIteration(iteration, numIterations, lastResults)

        return results

    def follow(self, userIds=None, keywords=None, locations=None, feedId=None):
        data = {}

        if userIds is not None:
            data['follow'] = ','.join(userIds)

        if keywords is not None and len(keywords) > 0:
            data['track'] = ','.join(keywords)

        result = ""
        if locations is not None and len(locations) > 0:
            for location in locations:
                x, y = location
                result += ',%f, %f' % (y, x) # twitter is opposite way round.
            result = result[1:]
            data['locations'] = result

        logger.info('Following twitter stream with parameters: userIds %s, keywords %s, locations %s' % (userIds, keywords, locations))

        def buildConnectionStream():
            try:
                response =  self._session.post('https://stream.twitter.com/1.1/statuses/filter.json',
                                               data,
                                               stream=True,
                                               timeout=Configuration.TWITTER_FEED_TIMEOUT_SECONDS)

                if not response.ok:
                    raise TwitterSession.SessionException('Response contains errors: %s' % response.reason)
            except (requests.ConnectionError, requests.HTTPError, TwitterSession.SessionException) as e:
                raise TwitterSession.SessionException('Failed to access twitter streaming API, reason: %s' % e.message)

            return response.iter_lines()

        return TwitterFeed(userIds, keywords, locations, buildConnectionStream, self, feedId)


class TwitterFeed(object):
    def __init__(self, userIds, keywords, locations, buildConnectionStreamFunc, twitterSession, feedId=None):
        super(TwitterFeed,self).__init__()

        if feedId is None:
            feedId = unicode(getUniqueId())

        assert buildConnectionStreamFunc is not None
        if twitterSession is not None:
            assert isinstance(twitterSession, TwitterSession)

        self.start_connection = buildConnectionStreamFunc

        self.restartConnection()
        self.twitter_session = twitterSession
        self.user_ids = userIds
        self.keywords = keywords
        self.locations = locations
        self.feed_id = feedId # for logging.

        # Twitter sends us one every second, we don't want to fill up the logs with this.
        self.logUndeliveredMessagesTimer = Timer(120000,True)

    def restartConnection(self):
        self._feed = self.start_connection()

    def __iter__(self):
        logPrefix = 'TWITTER STREAM MESSAGE: '
        def doLog(message):
            logger.warn('%s (%s): %s' % (logPrefix, self.feed_id, unicode(message)))

        for x in self._feed:
            if self.twitter_session is not None and not self.twitter_session.is_session_active:
                return

            # I think keep alive is actually done inside requests now
            # so this will probably never happen.
            if x is None or len(x) == 0:
                doLog('Keep alive signal received')
                continue

            try:
                data = json.JSONDecoder(strict=False).decode(x)
                tree = Tree.make(data)
            except ValueError as e:
                doLog('ValueError while decoding tweet: %s' % e.message)
                continue

            if tree.getFromTree(['delete']) is not None:
                statusId = tree.getFromTree(['delete','status','id'])
                userId = tree.getFromTree(['delete','status','user_id'])
                doLog('Deletion request received for userId: %s, statusId: %s' % (unicode(userId), unicode(statusId)))
            elif tree.getFromTree(['scrub_geo']) is not None:
                userId = tree.getFromTree(['scrub_geo','user_id'])
                upToStatusId = tree.getFromTree(['scrub_geo','up_to_status_id'])
                doLog('Geolocated tweet strip request received for userId: %s, for tweets up to ID: %s' % (unicode(userId), unicode(upToStatusId)))
            elif tree.getFromTree(['limit']) is not None:
                if self.logUndeliveredMessagesTimer.ticked():
                    undeliveredMessagesUntilNow = tree.getFromTree(['limit','track'])
                    doLog('From feed connection time until now (reconnects reset the count), %s tweets were not delivered due to rate limitations imposed by Twitter' % unicode(undeliveredMessagesUntilNow))
            elif tree.getFromTree(['status_withheld']) is not None:
                withheldStatusId = tree.getFromTree(['status_withheld','id'])
                withheldUserId = tree.getFromTree(['status_withheld','user_id'])
                withheldInCountries = tree.getFromTree(['status_withheld','withheld_in_countries'])
                doLog('Status with ID: %s from user with ID: %s has been withheld in the following countries: %s' % (unicode(withheldStatusId, unicode(withheldUserId), unicode(withheldInCountries))))
            elif tree.getFromTree(['user_withheld']) is not None:
                withheldUserId = tree.getFromTree(['user_withheld'])
                withheldInCountries = tree.getFromTree(['user_withheld','withheld_in_countries'])
                doLog('User with ID: %s has been withheld in the following countries: %s' % (unicode(withheldUserId), unicode(withheldInCountries)))
            elif tree.getFromTree(['disconnect']) is not None:
                disconnectCode = tree.getFromTree(['disconnect','code'])
                disconnectStreamName = tree.getFromTree(['disconnect','stream_name'])
                disconnectReason = tree.getFromTree(['disconnect','reason'])
                doLog('Stream with name "%s" disconnected from server, code: %s, reason: %s' % (unicode(disconnectStreamName), unicode(disconnectCode), unicode(disconnectReason)))
                raise TwitterSession.SessionException('Disconnected from server')
            elif tree.getFromTree(['warning']) is not None:
                stallCode = tree.getFromTree(['warning','code'])
                stallMessage = tree.getFromTree(['warning','message'])
                stallPercentFull = tree.getFromTree(['warning','percent_full'])
                doLog('Stall warning received with stall code: %s, message: %s, percent full: %s' % (unicode(stallCode), unicode(stallMessage), unicode(stallPercentFull)))
            else:
                yield Tweet(data, self.twitter_session)



class UserFollowerEnrichmentProgress(object):
    """ This class provides a callback interface
        using the signal handler system, so that
        other modules can keep track of the enrichment
        process on a per user basis. """

    def __init__(self, encapsulatingUser):
        super(UserFollowerEnrichmentProgress,self).__init__()

        assert isinstance(encapsulatingUser, User)

        self.starting_position = 0
        self.encapsulating_user = encapsulatingUser

        self.user_progress = 0.0
        self.queue_progress = 0.0
        self.user_id_progress = 0.0
        self.enrichment_progress_description = ''
        self.queue_waiting_for_user = None

    def merge(self, source):
        if self is source:
            return 0,0,0

        assert isinstance(source, UserFollowerEnrichmentProgress)
        difUserProgress = source.user_progress - self.user_progress
        difUserIdProgress = source.user_id_progress - self.user_id_progress
        difQueueProgress = source.queue_progress - self.queue_progress

        # Progress should never go backwards. We can arrive at this situation if
        # we receive a tweet (which will have progress 0,0,0) while we are enriching
        # follower data.
        if difUserProgress >= 0 and difUserIdProgress >= 0 and difQueueProgress >= 0:
            self.starting_position = source.starting_position
            self.encapsulating_user = source.encapsulating_user
            self.user_progress = source.user_progress
            self.queue_progress = source.queue_progress
            self.user_id_progress = source.user_id_progress
            self.enrichment_progress_description = source.enrichment_progress_description
            self.queue_waiting_for_user = source.queue_waiting_for_user

            return difQueueProgress, difUserIdProgress, difUserProgress
        else:
            return 0,0,0

    def getTuple(self):
        return self.queue_progress,\
               self.user_progress,\
               self.user_id_progress,\
               self.enrichment_progress_description,\
               self.queue_waiting_for_user

    def loadFromTuple(self, t):
        if t is not None:
            (self.queue_progress,
            self.user_progress,
            self.user_id_progress,
            self.enrichment_progress_description,
            self.queue_waiting_for_user) = t



    @staticmethod
    def getPercentageFromQueuePosition(queuePosition, queueSize):
        if queueSize > 0:
            percentage = (float(queueSize-queuePosition) / queueSize) * 100.0
        else:
            percentage = float(0)

        return percentage

    @staticmethod
    def getPercentageFromIteration(iteration, numIterations):
        if numIterations > 0:
            percentage = (float(iteration) / float(numIterations)) * 100.0
        else:
            percentage = float(0)

        return percentage

    def onQueuePositionChange(self, _, position, waitingForUser):
        position += 1

        if self.starting_position < position:
            self.starting_position = position

        percentage = UserFollowerEnrichmentProgress.getPercentageFromQueuePosition(position, self.starting_position)
        percentage /= 3.0

        self.queue_progress = percentage
        self.queue_waiting_for_user = waitingForUser

        descriptionInBrackets = 'position %d' % position

        if waitingForUser is not None:
            assert isinstance(waitingForUser, User)
            descriptionInBrackets += ' - waiting on user: %s'

        self.enrichment_progress_description = "<p>Waiting in queue (%s)...</p>"  % descriptionInBrackets

    def onUserEnrichmentIteration(self,iteration,total):
        percentage = UserFollowerEnrichmentProgress.getPercentageFromIteration(iteration, total)
        percentage /= 3.0

        self.user_progress = percentage
        self.enrichment_progress_description = "<p>Retrieving user IDs of followers (%d / %d)...</p>" % (iteration, total)
        self.queue_waiting_for_user = None


    def onUserIdEnrichmentIteration(self,iteration,total):
        percentage = UserFollowerEnrichmentProgress.getPercentageFromIteration(iteration, total)
        percentage /= 3.0

        self.user_id_progress = percentage
        self.enrichment_progress_description = "<p>Retrieving data of followers (%d / %d)...</p>" % (iteration, total)
        self.queue_waiting_for_user = None


class UserAnalysis(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        super(UserAnalysis, self).__init__()

    @abstractmethod
    def onFollower(self, follower):
        """ Called when a follower is loaded for the user which encapsulates this object. """
        pass

    @abstractproperty
    def results(self):
        """ Results in a basic form useful for programatic analysis. """
        pass

    @abstractproperty
    def results_cacheable(self):
        """ @return results suitable for caching in mongodb. """
        pass

    @abstractproperty
    def results_viewable(self):
        """ @return viewable results suitable for displaying in text form.
            This is used when sending data to clients via file download. """
        pass

    @abstractproperty
    def analysis_name(self):
        pass

    @abstractmethod
    def from_cache(self, cacheData):
        pass

class UserAnalysisFollowersGeocoded(UserAnalysis):
    """ Light weight analysis of follower locations. """

    def __init__(self):
        super(UserAnalysisFollowersGeocoded,self).__init__()

        self.num_geocoded_followers_by_location = dict()

        self.num_followers = 0
        self.num_non_geocoded_followers = 0
        self.num_geocoded_followers = 0

    @staticmethod
    def analysis_name_static():
        return 'followers_geocoded'

    @property
    def analysis_name(self):
        return UserAnalysisFollowersGeocoded.analysis_name_static()

    def onGeocodedFollower(self, location):
        assert isinstance(location, GeocodeResultAbstract)
        self.num_geocoded_followers_by_location[location] = self.num_geocoded_followers_by_location.setdefault(location,0) + 1
        self.num_geocoded_followers += 1

    def onFollower(self, follower):
        if follower.is_geocoded:
            self.onGeocodedFollower(follower.location_geocode)
        else:
            self.num_non_geocoded_followers += 1

        self.num_followers += 1

    @property
    def results(self):
        sortableList = list()
        for location, numFollowers in self.num_geocoded_followers_by_location.iteritems():
            sortableList.append((location, numFollowers))

        sortableList.append((GeocodeResultFailed(),self.num_non_geocoded_followers))

        return sorted(sortableList, key = lambda value: value[1], reverse=True)

    @property
    def results_cacheable(self):
        geocoded = []
        for key, value in self.num_geocoded_followers_by_location.iteritems():
            assert isinstance(key, GeocodeResultAbstract)
            geocoded.append({'_id' : key.cache_id, 'quantity' : value})

        return {'geocoded_followers_by_location' : geocoded,
                'num_followers' : self.num_followers,
                'num_non_geocoded_followers' : self.num_non_geocoded_followers,
                'num_geocoded_followers' : self.num_geocoded_followers}

    @property
    def results_viewable(self):
        geocodedFollowersByLocation = []
        for location, numFollowers in self.num_geocoded_followers_by_location.iteritems():
            assert isinstance(location, GeocodeResultAbstract)
            geocodedFollowersByLocation.append((location.cache_id, location.display_name, numFollowers))

        return {'geocoded_followers_by_location' : geocodedFollowersByLocation,
                'num_followers' : self.num_followers,
                'num_non_geocoded_followers' : self.num_non_geocoded_followers,
                'num_geocoded_followers' : self.num_geocoded_followers}


    def from_cache(self, data):
        geocoded = data['geocoded_followers_by_location']
        for item in geocoded:
            theId = item['_id']
            quantity = item['quantity']

            geocodeResult = geocodeFromCacheById(theId)
            if geocodeResult is None:
                logger.error('Failed to find geocode data in cache with ID: %s, while processing followers analysis result' % str(theId))

            self.onGeocodedFollower(geocodeResult)
            self.num_geocoded_followers_by_location[geocodeResult] = quantity

        self.num_followers =                data['num_followers']
        self.num_non_geocoded_followers =   data['num_non_geocoded_followers']
        self.num_geocoded_followers =       data['num_geocoded_followers']

def buildAnalyserFromName(name):
    if name == UserAnalysisFollowersGeocoded.analysis_name_static():
        return UserAnalysisFollowersGeocoded()
    else:
        logger.error('Cannot create user analysis with name: %s, name is unknown' % name)
        return None

class UserGeocodeConfig(object):
    def __init__(self, providerId, acceptablePlaceTypes=None, requiredTwitterPlaceTypes=None):
        super(UserGeocodeConfig,self).__init__()

        if acceptablePlaceTypes is None:
            acceptablePlaceTypes = (GeocodeResultAbstract.PlaceTypes.CITY,)

        if requiredTwitterPlaceTypes is None:
            requiredTwitterPlaceTypes = (Place.Type.CITY,)

        self.acceptable_place_types = acceptablePlaceTypes
        self.required_twitter_place_types = requiredTwitterPlaceTypes
        self.provider_id = providerId

class User(Hashable, Timestamped):
    def __init__(self, userJson, twitterSession, fromCache=False, isFollowee=False, isAssociatedWithTweet=False, twitterPlace=None, currentLocationCoordinate=None, geocodeBias=None, knownFollowees=None):
        Hashable.__init__(self)
        Timestamped.__init__(self)

        if twitterSession is not None:
            assert isinstance(twitterSession, TwitterSession)

        if twitterPlace is not None:
            assert isinstance(twitterPlace, Place)

        if knownFollowees is None:
            knownFollowees = set()

        self.allow_geocode_external = True

        if userJson is None:
            self.data = Tree.make()
        else:
            self.data = Tree.make(userJson)

        # If false indicates that self.data is already in the cache,
        # so no point readding.
        self.isDataNew = not fromCache

        self.is_followee = isFollowee

        # This does not contain all followees, only followees known to our application
        # through follower enrichment.
        self.known_followees = knownFollowees

        self.is_associated_with_tweet = isAssociatedWithTweet
        self.twitter_session = twitterSession

        if twitterSession is not None:
            self.instance_key = twitterSession.instance_key
        else:
            self.instance_key = None

        self.queued_for_follower_enrichment = False
        self.current_location_coordinate = currentLocationCoordinate

        self.twitter_place = twitterPlace

        self.last_follower_enrichment_error = None
        self.follower_enrichment_progress = UserFollowerEnrichmentProgress(self)

        if self.num_followers is not None:
            self.twitter_calls_to_retrieve_follower_ids = math.ceil(float(self.num_followers) / float(TwitterSession.GET_FOLLOWER_IDS_QUANTITY_PER_TWITTER_CALL))
        else:
            self.twitter_calls_to_retrieve_follower_ids = 1

        self.geocoded_from = None
        self.geocode_bias = None

        self.analysers = None

    def setTwitterSession(self, twitterSession):
        self.instance_key = twitterSession.instance_key
        self.twitter_session = twitterSession

        if self.is_followers_loaded:
            for follower in self.followers:
                assert isinstance(follower,User)
                follower.setTwitterSession(self.twitter_session)

    def addAnalyser(self, analyser):
        assert isinstance(analyser, UserAnalysis)
        if self.analysers is None:
            self.analysers = dict()

        self.analysers[analyser.analysis_name] = analyser

    @property
    def has_analysers(self):
        return self.analysers is not None and len(self.analysers) > 0

    def isAnalyserLoaded(self, analyser):
        assert isinstance(analyser, UserAnalysis)
        if not self.has_analysers:
            return False

        return analyser.analysis_name in self.analysers

    def analyseFollower(self, follower):
        assert isinstance(follower, User)
        if not self.has_analysers:
            return

        for value in self.analysers.values():
            value.onFollower(follower)

    @classmethod
    def Id(cls, theId, twitterSession):
        aux = cls(None, twitterSession)
        aux.data.addToTree(theId,['id'])
        return aux

    @classmethod
    def FromCache(cls, jsonData, twitterSession, timestamp, locationGeocode, followerEnrichmentProgressTuple,
                  geocode_bias, geocode_from, is_followee, is_associated_with_tweet,
                  last_follower_enrichment_error, known_followees, place, queued_for_follower_enrichment):
        item = cls(jsonData, twitterSession, fromCache=True)
        item.timestamp = timestamp
        item._locationGeocode = locationGeocode

        if followerEnrichmentProgressTuple is not None:
            item.follower_enrichment_progress.loadFromTuple(followerEnrichmentProgressTuple)

        if geocode_bias is not None:
            item.geocode_bias = geocode_bias

        if geocode_from is not None:
            item.geocoded_from = geocode_from

        if is_followee is not None:
            item.is_followee = is_followee

        if is_associated_with_tweet is not None:
            item.is_associated_with_tweet = is_associated_with_tweet

        if last_follower_enrichment_error is not None:
            item.last_follower_enrichment_error = last_follower_enrichment_error

        if known_followees is not None:
            item.known_followees = known_followees

        if place is not None:
            item.twitter_place = place

        if queued_for_follower_enrichment is not None:
            item.queued_for_follower_enrichment = queued_for_follower_enrichment

        return item

    def loadFollowers(self, followerIdsList, followersList):
        assert followersList is not None
        if followerIdsList is None:
            followerIdsList = []
        else:
            assert len(followerIdsList) == len(followersList)

        self._follower_ids = followerIdsList
        self._followers = followersList

    def merge(self, otherItem):
        """ Merges data such as geocoding and followers into this object,
            will fail if users are not he same; you should not try to merge two
            different users."""
        assert isinstance(otherItem, User)
        assert self.id == otherItem.id

        if not self.queued_for_follower_enrichment and otherItem.queued_for_follower_enrichment:
            self.queued_for_follower_enrichment = otherItem.queued_for_follower_enrichment
        elif self.queued_for_follower_enrichment and ((not otherItem.queued_for_follower_enrichment) and otherItem.is_followers_loaded):
            self.queued_for_follower_enrichment = False

        if not self.is_geocoded and otherItem.is_geocoded:
            self._locationGeocode = otherItem._locationGeocode

        if not self.is_follower_ids_loaded and otherItem.is_follower_ids_loaded:
            self._follower_ids = otherItem._follower_ids

        if not self.is_followers_loaded and otherItem.is_followers_loaded:
            self._followers = otherItem.followers

        if not self.is_followee and otherItem.is_followee:
            self.is_followee = otherItem.is_followee

        if not self.is_associated_with_tweet and otherItem.is_associated_with_tweet:
            self.is_associated_with_tweet = otherItem.is_associated_with_tweet

        if not self.has_twitter_place and otherItem.has_twitter_place:
            self.twitter_place = otherItem.twitter_place

        if otherItem.current_location_coordinate is not None:
            self.current_location_coordinate = otherItem.current_location_coordinate

        self.addFollowees(otherItem.known_followees)

        if otherItem.has_analysers:
            for value in otherItem.analysers.values():
                self.addAnalyser(value)

        return self.follower_enrichment_progress.merge(otherItem.follower_enrichment_progress)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        if self.id is not None:
            return '<User - %d>' % self.id
        else:
            return '<User>'

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return hash(self) == hash(other)

    def addFollowee(self, followee):
        assert isinstance(followee, User)
        self.known_followees.add(followee)

    def addFollowees(self, followees):
        self.known_followees |= followees

    @property
    def has_current_location_coordinate(self):
        return self.current_location_coordinate is not None

    @property
    def current_location_coordinate_string(self):
        if self.current_location_coordinate is not None and len(self.current_location_coordinate) >= 2:
            return '%d, %d' % (self.current_location_coordinate[0], self.current_location_coordinate[1])
        else:
            return None

    @property
    def num_followers(self):
        return self.data.getFromTree(['followers_count'])

    @property
    def profile_image_url(self):
        return self.data.getFromTree(['profile_image_url'])

    @property
    def follower_ids(self):
        return self.getFollowerIds()

    @property
    def follower_ids_string(self):
        if not self.is_follower_ids_loaded:
            return ''

        return ','.join(str(n) for n in self.follower_ids)

    @property
    def followee_ids_string(self):
        if not self.has_followees:
            return ''

        return ','.join(str(n.id) for n in self.known_followees)

    @property
    def has_followees(self):
        return len(self.known_followees) > 0

    @property
    def followers(self):
        return self.getFollowers()

    def getFollowerIds(self, pFuncIteration=None):
        def funcIteration(userId, iteration):
            totalIterations = self.twitter_calls_to_retrieve_follower_ids + 1
            if self.follower_enrichment_progress is not None:
                self.follower_enrichment_progress.onUserEnrichmentIteration(iteration, totalIterations)

            if pFuncIteration is not None:
                return pFuncIteration(userId, iteration, totalIterations)

        try:
            return self._follower_ids
        except AttributeError:
            if self.twitter_session is None:
                self._follower_ids = None
                logger.warn("Failed to load follower IDs because user object has no link to twitter")
            else:
                try:
                    self._follower_ids = self.twitter_session.getFollowerIds(self.id, funcIteration=funcIteration)
                except TwitterSession.SessionException as e:
                    logger.warn('Failed to retrieve follower IDs of user: %d' % self.id)
                    self.last_follower_enrichment_error = str(e)
                    self._follower_ids = None

            return self._follower_ids

    def getFollowers(self, pFuncIteration=None):
        geocode_bias_for_followers = self.geocode_bias_for_followers
        userId = self.id

        def funcIteration(iteration, totalIterations, followersFromLastIteration):
            # Set bias of followers - makes them prioritise locations closer to us.
            for follower in followersFromLastIteration:
                assert isinstance(follower, User)
                follower.geocode_bias = geocode_bias_for_followers

            if self.follower_enrichment_progress is not None:
                self.follower_enrichment_progress.onUserIdEnrichmentIteration(iteration, totalIterations)

            if pFuncIteration is not None:
                return pFuncIteration(userId, iteration, totalIterations, followersFromLastIteration)

        try:
            return self._followers
        except AttributeError:
            ids = self.follower_ids
            if ids is None:
                logger.warn("Failed to load followers because follower IDs could not be loaded")
                self._followers = None
                return None

            if self.twitter_session is None:
                self._followers = None
                logger.warn("Failed to load follower information because user object has no link to twitter")
            else:
                try:
                    self._followers = self.twitter_session.getUsersFromIds(self, ids, funcIteration=funcIteration)
                except TwitterSession.SessionException as e:
                    logger.warn('Failed to retrieve follower user IDs of user: %d' % self.id)
                    self.last_follower_enrichment_error = str(e)
                    self._followers = None

            return self._followers

    @property
    def geocode_bias_for_followers(self):
        if self.is_geocoded:
            return self.location_geocode.coordinate

        return None

    @property
    def is_followers_loaded(self):
        return hasattr(self, '_followers') and self._followers is not None

    @property
    def is_follower_ids_loaded(self):
        return hasattr(self, '_follower_ids') and self._follower_ids is not None

    @property
    def name(self):
        return self.data.getFromTree(['name'])

    @property
    def id(self):
        return self.data.getFromTree(['id'])

    @property
    def num_followers(self):
        return self.data.getFromTree(['followers_count'])

    @property
    def description(self):
        return self.data.getFromTree(['description'])

    @property
    def location_text(self):
        return self.data.getFromTree(['location'])

    @property
    def has_location(self):
        return self.location_text is not None and len(self.location_text) > 0

    @property
    def has_twitter_place(self):
        return self.twitter_place is not None

    @property
    def location_geocode(self):
        try:
            return self._locationGeocode
        except AttributeError:
            logger.error('Call made to location_geocode before geocodeLocationFromCache or External')
            raise

    @property
    def is_geocoded(self):
        return hasattr(self, '_locationGeocode') and self._locationGeocode is not None

    @property
    def geocode_bias(self):
        return self._geocode_bias

    @geocode_bias.setter
    def geocode_bias(self, bias):
        # Most acurate source will be where twitter
        # says the user is.
        if self.has_twitter_place:
            self._geocode_bias = self.twitter_place.coordinate
            return

        self._geocode_bias = bias

    def _setGeocodeDescription(self, placeNameSource, dataSource, bias):
        result = '%s / %s' % (placeNameSource, dataSource)
        if bias is not None:
            x,y = bias
            result = '%s - bias: (%.1f, %.1f)' % (result,x,y)

        self.geocoded_from = result
        return result

    def clearGeocode(self, resetOnlyIfGeocodeFailed=False):
        try:
            if not resetOnlyIfGeocodeFailed or self._locationGeocode is None:
                del self._locationGeocode
        except AttributeError:
            pass

    def __doGeocode(self, geocodeConfig, geocodeFunc):
        assert isinstance(geocodeConfig, UserGeocodeConfig)

        try:
            # Already geocoded if no exception thrown.
            return self._locationGeocode is not None
        except AttributeError:
            pass

        def doGenericGeocode(geocodeExplain, countryCode, geocodeText):
            if geocodeText is None or len(geocodeText) < 1:
                return None

            return geocodeFunc(geocodeExplain, geocodeConfig.provider_id, geocodeConfig.acceptable_place_types, self.geocode_bias, countryCode, geocodeText)

        # Try using data from twitter first.
        if self.has_twitter_place:
            countryCode = self.twitter_place.country_code

            # Only if twitter place is of correct type.
            if geocodeConfig.required_twitter_place_types is None or self.twitter_place.place_type in geocodeConfig.required_twitter_place_types:
                def doTwitterPlaceGeocode(geocodeText):
                    return doGenericGeocode('Twitter place data', self.twitter_place.country_code, geocodeText)

                # Try both full and short name.
                self._locationGeocode = doTwitterPlaceGeocode(self.twitter_place.full_name)
                if self._locationGeocode is not None:
                    return True

                self._locationGeocode = doTwitterPlaceGeocode(self.twitter_place.short_name)
                if self._locationGeocode is not None:
                    return True
        else:
            countryCode = None

        # Use location field.
        if self.has_location:
            self._locationGeocode = doGenericGeocode('Location field', countryCode, self.location_text)
        else:
            # Give up now.
            self._locationGeocode = None

        return self._locationGeocode is not None

    def geocodeLocationFromCache(self, geocodeConfig, inMemoryOnly=None):
        def geocodeFunc(geocodeExplain, providerId, acceptableTypes, geocodeBias, countryCode, geocodeText):
            result = geocodeFromCache(geocodeText, providerId, countryCode=countryCode, acceptableTypes=acceptableTypes, biasCoord=geocodeBias, inMemoryOnly=inMemoryOnly)
            if result is not None:
                self._setGeocodeDescription(geocodeExplain,'Cache',geocodeBias)
            return result

        return self.__doGeocode(geocodeConfig, geocodeFunc)

    def geocodeLocationFromExternal(self, geocodeConfig, retry=2):
        def geocodeFunc(geocodeExplain, providerId, acceptableTypes, geocodeBias, countryCode, geocodeText):
            result = geocodeFromExternalAndWriteToCache(geocodeText, providerId, countryCode=countryCode, acceptableTypes=acceptableTypes, biasCoord=geocodeBias, retry=retry)
            if result is not None:
                self._setGeocodeDescription(geocodeExplain,'External',geocodeBias)
            return result

        return self.__doGeocode(geocodeConfig, geocodeFunc)

class Place(Hashable):
    class Type:
        CITY = 'city'

    def __init__(self, data):
        self.data = Tree.make(data)

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        return hash(self) == hash(other)

    @classmethod
    def FromCache(cls, data):
        return cls(data)

    @property
    def id(self):
        return self.data.getFromTree(['id'])

    @property
    def country(self):
        return self.data.getFromTree(['country'])

    @property
    def country_code(self):
        return self.data.getFromTree(['country_code'])

    @property
    def full_name(self):
        return self.data.getFromTree(['full_name'])

    @property
    def short_name(self):
        return self.data.getFromTree(['name'])

    @property
    def place_type(self):
        return self.data.getFromTree(['place_type'])

    @property
    def is_city(self):
        return self.place_type == Place.Type.CITY

    @property
    def bounding_box(self):
        try:
            return self._bounding_box
        except AttributeError:
            box = self.data.getFromTree(['bounding_box','coordinates'])
            if box is None or len(box) < 1:
                self._bounding_box = None
                return None
            else:
                box = box[0]
                newBox = []
                for item in box:
                    newBox.append(reverse_list(item))

                if len(newBox) < 4:
                    self._bounding_box = None
                    return None

                self._bounding_box = newBox
                return self._bounding_box


    @property
    def coordinate(self):
        try:
            return self._coordinate
        except AttributeError:
            boundingBox = self.bounding_box
            if boundingBox is None:
                self._coordinate = None
                return None

            self._coordinate = getMidPointBox(self.bounding_box[0],
                                              self.bounding_box[1],
                                              self.bounding_box[2],
                                              self.bounding_box[3])
            return self._coordinate

    @property
    def coordinate_string(self):
        if self.coordinate is not None and len(self.coordinate) >= 2:
            return '%d, %d' % (self.coordinate[0], self.coordinate[1])
        else:
            return None



class Tweet(Hashable, Timestamped):
    def __init__(self, data, twitterSession, fromCache=False):
        Timestamped.__init__(self)
        Hashable.__init__(self)

        if twitterSession is not None:
            assert isinstance(twitterSession, TwitterSession)


        self.data = Tree.make(data)
        if not fromCache:
            self.data.applyFunctionInTree(reverse_list, ['coordinates', 'coordinates']) # for use with leaflet.

        self.isDataNew = not fromCache

        twitterPlaceData = self.data.getFromTree(['place'])
        if twitterPlaceData is not None:
            self.twitter_place = Place(twitterPlaceData)
        else:
            self.twitter_place = None

        userJson = self.data.getFromTree(['user'])
        if userJson is None:
            self._user = None
        else:
            self._user = User(userJson, twitterSession=twitterSession, isAssociatedWithTweet=True, twitterPlace=self.twitter_place, currentLocationCoordinate=self.coordinate)

        if twitterSession is not None:
            self.instance_key = twitterSession.instance_key
        else:
            self.instance_key = None

        self.twitter_session = twitterSession

    def setTwitterSession(self, twitterSession):
        if self.has_user:
            self.user.setTwitterSession(twitterSession)

        self.instance_key = twitterSession.instance_key
        self.twitter_session = twitterSession

    @classmethod
    def FromCache(cls, jsonData, twitterSession, timestamp, locationGeocode):
        item = cls(jsonData, twitterSession, True)
        item.timestamp = timestamp

        if item.has_user:
            item.user._locationGeocode = locationGeocode
            item.user.timestamp = timestamp

        return item

    def __unicode__(self):
        return self.text

    def __repr__(self):
        return '<Tweet - %s,%s>' % (self.created_at, self.user)

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        if not isinstance(other, Tweet):
            return False

        return hash(self) == hash(other)

    @property
    def id(self):
        return self.data.getFromTree(['id'])

    @property
    def created_at(self):
        return self.data.getFromTree(['created_at'])

    @property
    def retweet_count(self):
        return self.data.getFromTree(['retweet_count'])

    @property
    def text(self):
        """ Returns the text of the status update """
        return self.data.getFromTree(['text'])

    @property
    def coordinate(self):
        return self.data.getFromTree(['coordinates', 'coordinates'])

    @property
    def coordinate_string(self):
        if self.coordinate is not None and len(self.coordinate) >= 2:
            return '%d, %d' % (self.coordinate[0], self.coordinate[1])
        else:
            return None

    @property
    def has_user(self):
        return self._user is not None

    @property
    def user(self):
        return self._user

    @user.setter
    def user(self, user):
        self._user = user

    @property
    def has_twitter_place(self):
        return self.twitter_place is not None