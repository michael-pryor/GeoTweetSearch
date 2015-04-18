import logging
from threading import RLock
import time
from pymongo.errors import DuplicateKeyError
from api.caching.tweet_user import writeTweetToCache, writeUserToCache, readUserFromCache, UserProjection
from api.config import Configuration
from api.core.data_structures.tree import TreeFunctioned
from api.core.signals.events import   EventSignaler
from api.core.threads_core import BaseThread
from api.core.utility import criticalSection, OrderedDictEx, EventFrequencyCounter
from api.geocode.geocode_shared import GeocodeResultAbstract
from api.twitter.feed import Tweet, User

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class RealtimePerformance(object):
    def __init__(self):
        super(RealtimePerformance,self).__init__()

        self.tweets_per_minute = EventFrequencyCounter(1000 * 5, 1000 * 60) # update every 5 seconds
        self.tweets_per_hour = EventFrequencyCounter(1000 * 60, 1000 * 60 * 60) # update every minute
        self.tweets_per_day = EventFrequencyCounter(1000 * 60 * 60, 1000 * 60 * 60 * 24) # update every hour

    def onTweet(self, tweet):
        assert isinstance(tweet, Tweet)
        self.tweets_per_minute.onEvent()
        self.tweets_per_hour.onEvent()
        self.tweets_per_day.onEvent()

class RealtimePerformanceContainer(object):
    def __init__(self):
        super(RealtimePerformanceContainer,self).__init__()

        self.instance_performance = dict()
        self.location_performance = dict()

        self.event_signaler = EventSignaler('realtime_performance')

    def onTweet(self, tweet):
        assert isinstance(tweet, Tweet)

        instancePerformance = self.instance_performance.setdefault(tweet.instance_key, {'success' : RealtimePerformance(), 'geocode_fail' : RealtimePerformance()})

        if tweet.has_user and tweet.user.is_geocoded:
            for location in tweet.user.location_geocode.all_geocode_results:
                locationPerformance = self.location_performance.setdefault(tweet.instance_key, dict()).setdefault(location, {'success': RealtimePerformance()})
                locationPerformance['success'].onTweet(tweet)
                
            instancePerformance['success'].onTweet(tweet)
        else:
            instancePerformance['geocode_fail'].onTweet(tweet)

    def signalUpdate(self):
        self.event_signaler.signalEvent({'instance_tweets' : self.instance_performance,
                                         'location_tweets' : self.location_performance})


class RealtimePerformanceThread(BaseThread):
    def __init__(self, realtimePerformanceContainer):
        super(RealtimePerformanceThread,self).__init__('RealtimePerformanceThread',None,True)

        assert isinstance(realtimePerformanceContainer, RealtimePerformanceContainer)
        self.realtime_performance_container = realtimePerformanceContainer

    def _run(self):
        while True:
            time.sleep(1)
            self.realtime_performance_container.signalUpdate()

class UsersByLocation(TreeFunctioned):
    """ A mapping from location to users (1 to many) """

    def __init__(self, funcGetInstance, funcGetGeocode, funcGetUser, funcGetValue=None, *args, **kwargs):
        super(UsersByLocation,self).__init__([funcGetInstance, funcGetGeocode, funcGetUser], funcGetValue, *args, **kwargs)

    @classmethod
    def User(cls):
        return cls(funcGetInstance=lambda user: user.instance_key,
                   funcGetGeocode=lambda user: user.location_geocode,
                   funcGetUser=lambda user: user,
                   funcGetValue=None)

class TweetsByLocation(TreeFunctioned):
    """ A mapping from location to tweets (1 to many) """

    BASE_DEPTH = 0
    LOCATION_BRANCH_DEPTH = 1

    def __init__(self, funcGetInstance, funcGetGeocode, funcGetTweet, funcGetValue=None, *args, **kwargs):
        super(TweetsByLocation,self).__init__([funcGetInstance, funcGetGeocode, funcGetTweet], funcGetValue, buildBranchFunc=self.onBranchCreation, *args, **kwargs)

    def onBranchCreation(self, depth):
        """ Restricts the number of tweets stored in memory.  """
        maxSize = None
        if depth == TweetsByLocation.BASE_DEPTH:
            maxSize = Configuration.MAX_SERVER_LIVE_LOCATIONS
        elif depth == TweetsByLocation.LOCATION_BRANCH_DEPTH:
            maxSize = Configuration.MAX_SERVER_LIVE_TWEETS
        else:
            logger.error('bad depth')

        return OrderedDictEx(fifo=True, maxSize=maxSize)

    @classmethod
    def Tweet(cls):
        def funcGeocode(tweet):
            result = list()

            baseLocation = tweet.user.location_geocode
            assert isinstance(baseLocation, GeocodeResultAbstract)
            result.append(baseLocation)

            if baseLocation.has_country:
                result.append(baseLocation.country)

            if baseLocation.has_continent:
                result.append(baseLocation.continent)

            return result

        return cls(funcGetInstance=lambda tweet: tweet.instance_key,
                   funcGetGeocode=(funcGeocode,True), # indicate that this is multi key.
                   funcGetTweet=lambda tweet: tweet,
                   funcGetValue=None)

class TreeSet(TreeFunctioned):
    """ A tree which acts like a set """

    def __init__(self, *args, **kwargs):
        super(TreeSet,self).__init__(hashFuncList=[lambda x: x.instance_key, lambda x: x], *args, **kwargs)

class DataSignalerStateless(object):
    def __init__(self, name):
        super(DataSignalerStateless,self).__init__()

        self.event_signaler = EventSignaler(key=name)

    def add(self, value):
        self.event_signaler.signalEvent({self.event_signaler.key : {'data' : value}})


class DataSignaler(object):
    def __init__(self, name, pruneFunc, data):
        super(DataSignaler, self).__init__()

        assert isinstance(data,TreeFunctioned)

        self.data = data
        self.event_signaler = EventSignaler(key=name)

        if pruneFunc is not None:
            assert callable(pruneFunc)

        self.prune_func = pruneFunc
        self._lock = RLock()

    def add(self, value):
        self._lock.acquire()

        try:
            self.data.addToTreeByFunction(value)
        finally:
            self._lock.release()

        data = {self.event_signaler.key : {'data': self.data}}
        self.event_signaler.signalEvent(data)

    def prune(self):
        if self.prune_func is not None:
            return criticalSection(self._lock, lambda: self.prune_func(dataStructure=self.data))

    def inByFunction(self, value, hashFuncList=None, depth=0):
       return criticalSection(self._lock, lambda: self.data.inByFunction(value, hashFuncList, depth))

    def getOriginalByFunction(self, value, hashFuncList=None, depth=0):
        return criticalSection(self._lock, lambda: self.data.getOriginalByFunction(value, hashFuncList, depth))


class DataCollection(object):
    """ Collective data store """

    def __init__(self):
        self.tweets_by_location = DataSignaler('tweets_by_location', None, TweetsByLocation.Tweet())
        self.all_users = DataSignalerStateless('all_users')

        self.realtime_performance = RealtimePerformanceContainer()
        self.realtime_performance_thread = RealtimePerformanceThread(self.realtime_performance)
        self.realtime_performance_thread.start()

    def prune(self):
        self.tweets_by_location.prune()

    def addFailGeocodeTweet(self, value):
        assert isinstance(value, Tweet)
        self.realtime_performance.onTweet(value)


    def addTweet(self, value):
        assert isinstance(value, Tweet)
        assert value.instance_key is not None
        assert value.twitter_session is not None

        if not value.twitter_session.is_session_active:
            logger.debug('Received tweet data but ignored it because instance is shutting down, instance: %s' % unicode(value.instance_key))
            return False

        # Update timestamp.
        # This might not be up to date if for example
        # we are reading from a file.
        value.touch()

        writeTweetToCache(value)

        self.realtime_performance.onTweet(value)

        # Don't insert if already there as data unlikely to have changed,
        # no point wasting resources writing again.
        self.addUser(value.user, False)
        self.tweets_by_location.add(value)
        return True

    def addUser(self, value, doUpdate):
        assert isinstance(value, User)
        assert value.instance_key is not None
        assert value.twitter_session is not None

        if not value.twitter_session.is_session_active:
            logger.debug('Received user data but ignored it because instance is shutting down, instance: %s' % unicode(value.instance_key))
            return False

        value.touch()

        self.all_users.add(value)

        try:
            writeUserToCache(value, doUpdate)
        except DuplicateKeyError:
            # We don't care, user data doesn't change much, so no point saturating disk with repeated
            # updates of users who tweet alot. The main purpose of user data is for storing follower information
            # anyways.
            pass

        return True

    def getUser(self, instance, userId, twitterSession, recursive=True, projection=None):
        return readUserFromCache(userId, twitterSession, instance, recursive, projection)

    def isDeepUserObjectIn(self, sourceUser):
        assert isinstance(sourceUser, User)

        cachedUser = readUserFromCache(sourceUser.id, sourceUser.twitter_session, sourceUser.instance_key, False, UserProjection.FollowerEnrichmentFlags())
        if cachedUser is None:
            return False

        assert isinstance(cachedUser, User)
        return cachedUser.is_followers_loaded or cachedUser.queued_for_follower_enrichment

    def removeInstanceData(self, instanceKey):
        if instanceKey in self.tweets_by_location.data:
            del self.tweets_by_location.data[instanceKey]
            return True
        else:
            return False