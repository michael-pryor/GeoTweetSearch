# This file contains all configuration options.
# Default values are loaded but are changed by configuration file loading.
#
# Configuration options should not be changed during runtime, they should be set
# when the server starts only.

# This is for use with leaflet, we get our map tiles from cloud made.
from ConfigParser import RawConfigParser
import logging
import math

GE_GOOGLE = 1
GE_MAP_QUEST = 2
GE_GEO_NET = 3

class Configuration:
    # The server listens for connections on this IP/port
    LISTEN_IP = '0.0.0.0'
    LISTEN_PORT = 8000

    # The server makes external connections to twitter, and geocoding services.
    # If we need to use a proxy we can.
    # This feeds into requests API.
    PROXIES_ENABLED = False
    PROXIES = {}

    # This is for use with leaflet js, we get our map tiles from cloud made.
    CLOUD_MADE_API_KEY = '52cb1eb007134446a590b6a9496a89d6'

    # Root of website.
    WEBSITE_ROOT = '127.0.0.1:8000'

    # Route on top of root website path, which takes us to
    # all static files. This can be changed freely.
    WEB_STATIC_ROUTE = '/static'

    # For 3 legged oauth, identifies our twitter application.
    CONSUMER_TOKEN = 'b10JtOqevg9v7pEUxMz1nw'
    CONSUMER_SECRET = 'osR8kld13H9MWeZ9G4X77c9uZBNBWAylVVmTEEZ0Hg'

    # MongoDB.
    MONGO_DB_IP = 'localhost'
    MONGO_DB_PORT = 27017
    MONGO_DB_DATABASE_NAME = 'mxp957'
    MONGO_DB_DATABASE_AUTHENTICATION_ENABLED = False
    MONGO_DB_DATABASE_AUTHENTICATION_USER_NAME = ''
    MONGO_DB_DATABASE_AUTHENTICATION_PASSWORD = ''

    # When enriching follower information of a user, we make several attempts in case we fail.
    MAX_FAILURES_ENRICH_USER_INFO = 4
    MAX_FAILURES_GET_FOLLOWERS = 4

    # If instance is not used it will be shut down and all data wiped.
    # This is time in milliseconds.
    # Usage = someone accessing a page.
    MAX_INSTANCE_INACTIVE_TIME_MS = 1000 * 60 * 60 # 1 hour.

    # If instance has been alive for this length of time it will be restarted.
    # This ensures that an instance does not grow infinitely large and use
    # all our storage.
    MAX_INSTANCE_TOTAL_AGE_MS = 1000 * 60 * 60 * 72 # 72 hours

    # Global flag, if false influence sources will not automatically enrich
    # follower information.
    AUTO_ENRICH_FOLLOWER_INFO_ENABLED = True

    # Maximum number of tweets per location per instance that
    # are 'live'. This means they are stored in memory and sent
    # to users when they first open the location page.
    #
    # The user's page will then continue to display additional tweets
    # up until MAX_CLIENT_LIVE_TWEETS.
    #
    # On the server and client side tweets are discarded in FIFO order.
    MAX_SERVER_LIVE_TWEETS = 20
    MAX_CLIENT_LIVE_TWEETS = 200

    # Server will store tweets for this many locations using the above
    # system of MAX_SERVER_LIVE_TWEETS and MAX_CLIENT_LIVE_TWEETS.
    #
    # The same FIFO order is used, resulting in least recently used behaviour.
    # This prevents memory leak issues.
    MAX_SERVER_LIVE_LOCATIONS = 1000

    # Twitter place data is ignored unless it is a type in this list.
    REQUIRED_TWITTER_PLACE_TYPES = ['city']


    # GE_GOOGLE and GE_MAP_QUEST are external data providers.
    # GE_GEO_NET represents internal memory that we load from a CSV file
    # containing country and continent information.
    # To switch between external providers you only need to change
    # GEOCODE_EXTERNAL_PROVIDER. Everything will run as normal without
    # further configuration changes.
    GEOCODE_EXTERNAL_PROVIDER = GE_MAP_QUEST

    # When users download CSV files, if we don't have information for a field
    # we will place this string in its place as a default value.
    CSV_EMPTY_VAL = '-'

    # For temporal data we collect it in groups known as 'temporal steps'.
    # The step represents the unit of time we can differentiate between.
    # So if the step is 1 hour, we can only view hour segments, and won't
    # be able to look at individual minutes within each hour.
    # However, the smaller the temporal step the more storage required.
    # This value is specified in milliseconds.
    TEMPORAL_STEP = 15 * 1000

    # We store geocode data in memory aswell as in the database for performance.
    # This value is the number of geocode entries to store in memory at any one time.
    # The in memory cache is a 'least recently used' cache.
    GEOCODE_IN_MEMORY_CACHE_SIZE = 30000 # holds actual place data.

    GEOCODE_QUERY_IN_MEMORY_CACHE_SIZE = 50000

    # Files to load GE_GEO_NET data from.
    COUNTRY_DATA_CSV = 'country_data.csv'
    CONTINENT_DATA_CSV = 'continent_data.csv'

    # Twitter specifies maximum 25 geographical areas may
    # be specified in connection to streaming API.
    # This value sets an input limit on the instance setup page.
    TWITTER_MAX_GEO_FILTERS = 25

    TWITTER_USERS_PER_USER_LOOKUP = 100
    TWITTER_USERS_PER_ID_LOOKUP = 5000
    TWITTER_RATE_LIMIT_WINDOW = 900000
    TWITTER_USERS_PER_USER_LOOKUP_RATE = 180
    TWITTER_USERS_PER_ID_LOOKUP_RATE = 15

    # Specifies whether bottle should operate in debug mode.
    BOTTLE_DEBUG = True

    # Maximum number of characters we display of the keywords list
    # in a short description of instance, this description is used
    # for example in the landing page below the instance map.
    INSTANCE_SHORT_DESCRIPTION_KEYWORDS_MAX_LENGTH = 90

    NUM_LANDING_PAGE_INSTANCES_PER_PAGE = 3

    # Must be multiple of 12.
    NUM_LANDING_PAGE_INSTANCES_PER_ROW = 3

    # Twitter feeds will be restarted regardless of error cause,
    # unless that feed has failed 4 times  where each
    # failure occurred 3 minutes (in addition to back off time - see back off config options)
    # since the last.
    #
    # Twitter feed failure does not cause application to exit.
    # It will cause only that instance to shut down.
    TWITTER_FEED_FAILURE_TIME_SPREAD = 1000 * 60 * 3
    TWITTER_FEED_FAILURE_CAP = 4

    # Critical threads failure will cause the application to exit.
    # See twitter feed failure above for info on these parameters.
    CRITICAL_THREAD_FAILURE_TIME_SPREAD = 1000 * 60 * 3
    CRITICAL_THREAD_FAILURE_CAP = 4

    # Twitter stream timeout
    # Keep alive signals are sent every 30 seconds, API documents recommend we wait
    # 90 seconds before timing out. Timeouts occur when no data is received for TWITTER_FEED_TIMEOUT
    # milliseconds.
    #
    # See document: https://dev.twitter.com/docs/streaming-apis/connecting.
    TWITTER_FEED_TIMEOUT_MS = 1000 * 90

    # Do not override this.
    TWITTER_FEED_TIMEOUT_SECONDS = float(TWITTER_FEED_TIMEOUT_MS) / 1000.0

    # Back off time = time after failure to wait before attempting restart.
    # Threads not listed here have no back off time because they don't
    # have external connections so are just processing data.
    #
    # Failures in other threads usually means a bug in our code.
    GEOCODE_FROM_EXTERNAL_THREAD_BACK_OFF_TIME = 3000
    GEOCODE_FROM_CACHE_THREAD_BACK_OFF_TIME = 5000
    TWITTER_FEED_THREAD_BACK_OFF_TIME = 3000

    # Users with this number of followers will be considered by the thread
    # which automatically enriches follower information. Users with more or less
    # followers will be ignored. Set to 0 and the option will be ignored, as
    # if there was no minimum or maximum.
    #
    # Consider making this an option as a part of instance setup.
    FOLLOWER_ENRICHMENT_GATE_THREAD_MINIMUM_FOLLOWERS = 25
    FOLLOWER_ENRICHMENT_GATE_THREAD_MAXIMUM_FOLLOWERS = 4000

    # Each instance has a queue which is added to periodically when
    # AUTO_ENRICH_FOLLOWER_INFO_ENABLED is true. We usually receive many
    # more tweets than can be added to this queue (without exhausting memory).
    # so to keep up we ignore a large number and only enrich when there is
    # space in the queue. This sets the queue size.
    #
    # Note that when a user of the website manually requests a user be enriched,
    # the user is added to the same queue, so making this too large increases the
    # wait time.
    FOLLOWER_ENRICHMENT_QUEUE_SIZE = 3

    # Maximum number of influence records to show in location page influence list.
    # We can end up with several hundred influence records which is too many
    # for browsers to display without slowing them down alot.
    DISPLAY_MAX_NUM_INFLUENCE_RECORDS_PER_PLACE_TYPE = 20

    LOG_DROP_AMOUNT_FREQ_MS = 60000

    PROJECT_NAME = 'GeoTweetSearch'

    NUM_GEOCODE_FROM_CACHE_WORKERS = 2
    NUM_ANALYSIS_WORKERS = 3
    NUM_GEOCODE_FROM_CACHE_WORKERS_MEMORY_ONLY = 2

    ANALYSIS_INPUT_THREAD_SIZE_CAP = 25
    GEOCODE_FROM_CACHE_PRIMARY_FAILURE_OUTPUT_QUEUE_SIZE = 10
    GEOCODE_FROM_EXTERNAL_INPUT_THREAD_SIZE_CAP_FOLLOWER_ENRICHMENT = 50
    GEOCODE_FROM_CACHE_INPUT_THREAD_SIZE_CAP = 200

    GEOCODE_FROM_CACHE_THREAD_WAIT_TIME_MS = 100

    ENABLE_MONGO_PROFILING = False
    MONGO_PROFILING_LEVEL = 1

    MONGO_EXPLAINS_ENABLED = False

    MONGO_OPERATION_TIMEOUT = 120000 # a.k.a socket timeout
    MONGO_CONNECTION_TIMEOUT = 60000

    MONGO_WRITE_CONCERN_ENABLED = True

    # See THREAD_FAILURE_DEFAULT_MAXIMUM_COUNT documentation.
    #
    # Thread failure count is reset after THREAD_FAILURE_DEFAULT_MAXIMUM_BACKOFF * 2 time, so
    # do not set this too high without changing that logic.
    #
    # Currently set to 15 minutes, so thread must be down for an hour to 'die', and must not fail for half an hour
    # after a failure in order to reset to a fully healthy thread.
    THREAD_FAILURE_DEFAULT_MAXIMUM_BACKOFF_MS = 900000

    # Default number of thread failures allowed before seen as 'dead' and special action taken.
    # Until this limit is reached the thread will be restarted without interruption to other threads.
    #
    # + 1 is because we start with a 1 second back off and double up, going 1, 2, 4, 8, 16 etc. seconds.
    # + N means once we hit the maximum back off we will do N additional back offs until giving up.
    #
    # A back off is time waited before attempting to restart a thread.
    THREAD_FAILURE_DEFAULT_MAXIMUM_COUNT = math.log(THREAD_FAILURE_DEFAULT_MAXIMUM_BACKOFF_MS / 1000,2) + 1 + 3



def loadConfigFromFile(configParser):
    logger = logging.getLogger(__name__)

    def setModuleAttr(key, value):
        setattr(Configuration, key, value)

    assert isinstance(configParser, RawConfigParser)

    s = 'main_config'

    glob = Configuration.__dict__
    for key, value in glob.iteritems():
        if not configParser.has_option(s, key) or key == '__name__':
            continue

        if isinstance(value,bool):
            setModuleAttr(key, configParser.getboolean(s, key))
        elif isinstance(value,int):
            setModuleAttr(key, configParser.getint(s, key))
        elif isinstance(value,list):
            setModuleAttr(key, configParser.get(s, key).split(','))
        elif isinstance(value, dict):
            resultDict = dict()
            data = configParser.get(s, key)
            data = data.split(',')
            for item in data:
                subKey, value = item.split('>')
                resultDict[subKey] = value

            setModuleAttr(key, resultDict)
        else:
            setModuleAttr(key, configParser.get(s, key))

        logger.info('Loaded from configuration file:\t %-50s = %-48s (type: %s)' % (unicode(key),unicode(glob[key]),unicode(type(glob[key]))))