__author__ = 'Michael Pryor'

if __name__ == '__main__':
    import ConfigParser
    import argparse
    import datetime
    import os
    import logging
    import sys
    from logging import config
    import bottle

    parser = argparse.ArgumentParser(description='Twitter Project', argument_default=argparse.SUPPRESS)
    parser.add_argument('--config',
                        metavar='file',
                        default='config.conf',
                        help='Configuration file to use')

    parser.add_argument('--logging_config',
                        metavar='file',
                        default='logging.conf',
                        help='Logging configuration file to use')

    parser.add_argument('--setup_instance_code',
                        default=False,
                        action='store_true',
                        help='The server does not run as normal, it will run in instance setup code mode.\n'
                             'Instance setup codes allow users to setup special instances with special'
                             'rules')

    parser.add_argument('--clear_instance_codes',
                        default=False,
                        action='store_true',
                        help='All instance codes will be wiped')

    parser.add_argument('--clear_geocode_data',
                        default=False,
                        action='store_true',
                        help='Clear all geocode data stored in the database')

    parser.add_argument('--wipe_instance_data',
                        default=False,
                        action='store_true',
                        help='Instance data is recovered from the database unless this flag is specified, in which case all instance data is wiped on startup')

    parser.add_argument('--show_database_storage_usage',
                        default=False,
                        action='store_true',
                        help='This will query all collections in the MongoDB database and show their size in megabytes.')

    parser.add_argument('--rebuild_instance_indexes',
                        default=False,
                        action='store_true',
                        help='Use with caution as it will lock up database until completed. Rebuilds indexes on instance collections.')

    parser.add_argument('--view_profiling_info',
                        default=False,
                        action='store_true',
                        help='If profiling is enabled in configuration the server logs MongoDB performance. Use this to retrieve the logged data.')

    parser._parse_known_args(sys.argv[1:], argparse.Namespace())
    args = parser.parse_args()

    loggingFile = args.logging_config
    logging.config.fileConfig(loggingFile,disable_existing_loggers=False)

    # Put this in all logs so we can clearly see when the server was restarted.
    logger = logging.getLogger(__name__)

    logger.critical('SERVER STARTED')

    logger.info('Using logging configuration file: "%s"' % loggingFile)

    configurationFile = args.config
    logger.info('Using configuration file: "%s"' % configurationFile)

    configParser = ConfigParser.SafeConfigParser()
    configParser.read(configurationFile)

    from api.config import loadConfigFromFile
    loadConfigFromFile(configParser)

    from api.core.utility import parseInteger, Timer
    from api.caching.instance_lifetime import getInstances
    from api.core.threads_core import BaseThread
    from api.web.twitter_instance import TwitterInstance
    from api.caching.instance_codes import resetCodeConsumerCounts, getInstanceCodeCollection, getCode
    from api.config import Configuration
    from api.caching.caching_shared import getCollections, getCollection, getDatabase
    from api.caching.temporal_analytics import isTemporalInfluenceCollection
    from api.caching.tweet_user import isUserCollection, isTweetCollection, getUserCollection, getTweetCollection
    from api.geocode.geocode_shared import GeocodeResultAbstract
    from api.core import threads
    from api.twitter.feed import UserAnalysisFollowersGeocoded, TwitterAuthentication
    from api.twitter.flow.display_instance_setup import GateInstance, StartInstancePost, ManageInstancePost
    from api.twitter.flow.display_oauth import OAuthSignIn, OAuthCallback
    from api.web import web_core
    from api.web.web_core import WebApplicationTwitter
    from api.twitter.flow.data_core import DataCollection
    from api.twitter.flow.display import LocationsMapPage, UserInformationPage, UserFollowerEnrichPage, TwitterCachePage, LocationsPage, BulkDownloadDataProvider, InfluenceCachePage, GeocodeCachePage, LandingPage
    from api.twitter.flow.web_socket_group import LocationMapWsg, TweetsByLocationWsg, UserWsg, BulkDownloadDataWsg, RealtimePerformanceWsg

    resetCodeConsumerCounts()

    if args.clear_instance_codes:
        logger.info('Clearing instance codes')
        getInstanceCodeCollection().drop()

    if Configuration.PROXIES_ENABLED:
        httpProxy = Configuration.PROXIES.get('http',None)
        httpsProxy = Configuration.PROXIES.get('https',None)

        # Requests API will use these environment variables.
        if httpProxy is not None:
            os.environ['HTTP_PROXY'] = Configuration.PROXIES['http']

        if httpsProxy is not None:
            os.environ['HTTPS_PROXY'] = Configuration.PROXIES['https']

    bottle.debug(Configuration.BOTTLE_DEBUG)

    GeocodeResultAbstract.initializeCountryContinentDataFromCsv()

    dataCollection = DataCollection()
    webApplication = WebApplicationTwitter(None, Configuration.MAX_INSTANCE_INACTIVE_TIME_MS, dataCollection)

    landingPage = LandingPage(webApplication)

    oauthSignIn = OAuthSignIn(webApplication, Configuration.CONSUMER_TOKEN, Configuration.CONSUMER_SECRET)
    oauthCallback = OAuthCallback(webApplication, Configuration.CONSUMER_TOKEN, Configuration.CONSUMER_SECRET, GateInstance.link_info.getPageLink())

    mapWebSocketGroup = LocationMapWsg(application=webApplication,locations=dataCollection.tweets_by_location)
    tweetsByLocationWebSocketGroup = TweetsByLocationWsg(application=webApplication,signaler=dataCollection.tweets_by_location)
    userInformationWebSocketGroup = UserWsg(application=webApplication, dataCollection=dataCollection, signaler=dataCollection.all_users)

    instanceGate = GateInstance(webApplication)
    startInstance = StartInstancePost(webApplication, Configuration.CONSUMER_TOKEN, Configuration.CONSUMER_SECRET, None)
    manageInstance = ManageInstancePost(webApplication)

    bulkDownloadDataProvider = BulkDownloadDataProvider(webApplication)
    bulkDownloadData = BulkDownloadDataWsg(webApplication, bulkDownloadDataProvider=bulkDownloadDataProvider)

    realtimePerformance = RealtimePerformanceWsg(webApplication, dataCollection.realtime_performance.event_signaler)

    locationDisplay = LocationsMapPage(webApplication, mapWebSocketGroup, bulkDownloadData, realtimePerformance)
    locationTextPage = LocationsPage(webApplication, tweetsByLocationWebSocketGroup, bulkDownloadData, realtimePerformance)
    userInformationPage = UserInformationPage(webApplication,userInformationWebSocketGroup)

    tweetPage = TwitterCachePage(webApplication)
    influencePage = InfluenceCachePage(webApplication)
    geocodeSearchPage = GeocodeCachePage(webApplication, Configuration.GEOCODE_EXTERNAL_PROVIDER)


    userAnalysers = [lambda user: UserAnalysisFollowersGeocoded()]

    # Setup all threads apart from twitter thread.
    resultDic = threads.startThreads(data=dataCollection,
                                     display=[mapWebSocketGroup,
                                              tweetsByLocationWebSocketGroup,
                                              userInformationWebSocketGroup,
                                              realtimePerformance],
                                     userAnalysers=userAnalysers)

    tweetQueue = resultDic['tweet_queue']
    followerExtractorGateThread = resultDic['follower_extractor_gate_thread']

    userEnrichFollowersPage = UserFollowerEnrichPage(webApplication, dataCollection, followerExtractorGateThread)

    # Load tweet queue into web application so that new instances can be created.
    webApplication.tweet_queue = tweetQueue

    assert webApplication.tweet_queue is not None

    if args.clear_geocode_data:
        logger.info('Clearing geocode data..')
        db = getDatabase()
        db.place.drop()
        db.geocode.drop()
        logger.info('Geocode data cleared')

    if args.setup_instance_code:
        print 'Running in setup instance code mode'

        try:
            while True:
                print 'Setting up instance code...'
                result = raw_input('Enter the maximum number of instances that can consume this code at any one time: ')
                result = parseInteger(result,0,default=1)

                code = getCode(result)
                print 'Instance code with ID: \'%s\' setup, with consume limit: %d' % (code, result)
        except KeyboardInterrupt:
            pass

        print 'Finished!'
        sys.exit(0)

    if args.show_database_storage_usage:
        f = open('db_results.txt', 'w')
        sys.stdout = f

        theStep = 1000 * 60 * 15
        print 'Running in show database storage mode, update every %dms' % theStep
        print
        f.flush()

        updateTimer = Timer(theStep,True)
        try:
            while True:
                updateTimer.waitForTick()

                collections = getCollections()
                print 'The time: %s'%  unicode(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                print 'Available collections: %s' % unicode(collections)
                print
                print
                print 'Database statistics: %s' % unicode(getDatabase().command({'dbStats' : 1}))

                for collection in collections:
                    print '%*s collection statistics: %s' % (20, collection, unicode(getDatabase().command({'collStats' : collection})))

                print
                print

                for collection in collections:
                    print 'Collection %s indxes: %s' % (collection, unicode(getCollection(collection).index_information()))
                print
                f.flush()

        except KeyboardInterrupt:
            print 'keyboard interupt'
            pass

        print 'Finished!'
        f.flush()
        sys.exit(0)

    if args.view_profiling_info:
        print 'Running profiling mode'

        try:
            while True:
                result = raw_input('Enter the minimum milliseconds: ')
                result = parseInteger(result,0,default=1)

                cursor = getDatabase().system.profile.find( { 'millis' : { '$gt' : result } } )
                for item in cursor:
                    print unicode(item)

        except KeyboardInterrupt:
            pass

        print 'Finished!'
        sys.exit(0)

    if args.wipe_instance_data:
        collections = getCollections()
        logger.info('Collections before startup clean: %s' % unicode(collections))

        for collection in collections:
            if isTemporalInfluenceCollection(collection) or \
                    isUserCollection(collection) or \
                    isTweetCollection(collection) or \
                            collection == 'twitter_place' or collection == 'instance_lifetime':
                logger.info('Dropping collection %s' % collection)
                getCollection(collection).drop()

        collections = getCollections()
        logger.info('Collections after startup clean: %s' % unicode(collections))
    else:
        logger.info('Loading instance data from database')

        count = [0]
        def onInstanceLoadFunc(instanceKey,
                               oauthToken,
                               oauthSecret,
                               geographicSetupString,
                               keywords,
                               instanceSetupCode,
                               startTime,
                               temporalLastTimeId,
                               count = count):
             temporal = dict()
             for providerId, value in temporalLastTimeId.iteritems():
                 providerId = int(providerId)
                 for placeId, timeId in value.iteritems():
                     placeId = int(placeId)
                     timeId = int(timeId)
                     temporal[GeocodeResultAbstract.buildCacheIdTuple(providerId, placeId)] = timeId
                     logger.debug('Loaded instance %s last temporal change source %d/%d -> %d' % (instanceKey, providerId, placeId, timeId))

             TwitterInstance(instanceKey,
                             webApplication.twitter_instances,
                             TwitterAuthentication(Configuration.CONSUMER_TOKEN, Configuration.CONSUMER_SECRET, oauthToken, oauthSecret),
                             unicode(geographicSetupString),
                             keywords,
                             instanceSetupCode,
                             startTime,
                             temporal,

                             # Critical because it once worked, if it fails when we restarted
                             # then maybe our server lost network connectivity.
                             isCritical = True)

             # can delete, was debugging indexes.
             if args.rebuild_instance_indexes:
                logger.info('Dropping indexes of instance %s' % instanceKey)
                getUserCollection(instanceKey).drop_indexes()
                getTweetCollection(instanceKey).drop_indexes()
             count[0] += 1

        getInstances(onInstanceLoadFunc)

        logger.info('Finished loading %d instances from database' % count[0])


    # We wrap the server management in a thread so that our failure handling code works.
    class WebServerThread(BaseThread):
        def __init__(self):
            super(WebServerThread,self).__init__('WebServerThread',None,True)

        def _run(self):
            web_core.startServer(Configuration.LISTEN_IP, Configuration.LISTEN_PORT, webApplication.bottle_app)

    # Start server and only exit application when it terminates.
    webServer = WebServerThread()
    webServer.start()

    webServer.join()