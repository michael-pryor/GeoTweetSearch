import logging
from math import ceil
from bottle import template, redirect, request, abort
from api.caching.temporal_analytics import getTemporalRange, getTemporalInfluenceCollection, getTimeIdFromTimestamp
from api.caching.tweet_user import readTweetsFromCache, readUsersFromCache, UserProjection, UserDataProjection
from api.config import Configuration
from api.core.threads import  FollowerExtractorGateThread
from api.core.utility import parseInteger, parseString, getDateTime, getEpochMs, splitList
from api.geocode.geocode_cached import geocodeFromCacheById, geocodeSearch
from api.geocode.geocode_shared import GeocodeResultAbstract
from api.twitter.feed import User, Tweet
from api.twitter.flow.data_core import DataCollection
from api.twitter.flow.display_core import Display, AsyncTunnelProviderFile
from api.twitter.flow.display_oauth import OAuthSignIn
from api.web.config import WEBSITE_ROOT_HTTP
from api.web.twitter_instance import TwitterInstance
from api.web.web_core import redirect_problem, WebApplicationTwitter

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)


def onDisplayUsageFunc(display, keys):
    instanceKey = keys.instance

    assert isinstance(display, Display)
    application = display.application

    assert isinstance(application, WebApplicationTwitter)
    instance = application.twitter_instances.getInstanceByInstanceKey(instanceKey)

    # This prevents instance from automatically being shut down.
    if instance is not None:
        instance.touch()

def getInstanceDescription(twitterInstance, includePrefix=True):
    if includePrefix:
        return 'Search stream %s' % twitterInstance.getShortDescription(False)
    else:
        return twitterInstance.getShortDescription(True)

def getHomeLink(projectName):
    return Display.getLink(LandingPage.link_info.getPageLink(),projectName,target='_self')

def getInstanceLink(twitterInstance):
    return LocationsMapPage.link_info.getPageLink(twitterInstance.instance_key)

class LocationsMapPage(Display):
    link_info = Display.LinkInfo(lambda link: lambda instance: link % instance, '/instance/%s')

    def __init__(self, application, mapWebSocketGroup, dataDownloadWebSocketManager, realTimePerformanceWebSocketGroup):
        assert isinstance(application, WebApplicationTwitter)

        Display.__init__(self,
                         application,
                         pageRoute=('/instance/<instance>', None),
                         webSocketManagers=[mapWebSocketGroup, dataDownloadWebSocketManager, realTimePerformanceWebSocketGroup],
                         onDisplayUsageFunc=onDisplayUsageFunc)
        self.locations = set()

    @property
    def page_html_function(self):
        def func(templateArguments, instance):
            instance = self.application.twitter_instances.getInstanceByInstanceKey(instance)
            if instance is None:
                abort(404, "No active search stream found at this address")

            assert isinstance(instance, TwitterInstance)

            keywords = instance.twitter_thread.twitter_feed.keywords
            geographicalSetupString = instance.geographic_setup_string

            if keywords is None:
                keywords = ''
                keywordsDisplay = '[None]'
            else:
                keywords = ','.join(keywords)
                keywordsDisplay = keywords

            instanceDescription = getInstanceDescription(instance, False)
            instanceDescriptionWithPrefix = getInstanceDescription(instance, True)

            homeLink = getHomeLink(Configuration.PROJECT_NAME)

            templateArguments.update({'instance_description' : instanceDescription,
                                      'instance_description_with_prefix' : instanceDescriptionWithPrefix,
                                      'home_link' : homeLink,
                                      'instance_name': instance.instance_key,
                                      'keywords': keywords,
                                      'keywords_display' : keywordsDisplay,
                                      'instance_map_data' : geographicalSetupString,
                                      'post_address': WEBSITE_ROOT_HTTP + '/manage_instance', # for terminate instance button.
                                      'login_address' : OAuthSignIn.link_info.getPageLink(),
                                      'start_epoch' : instance.constructed_at,
                                      'server_current_epoch' : getEpochMs()})

            return template('locations-map.tpl', templateArguments)

        return func


class UserInformationPage(Display):
    link_info = Display.LinkInfo(lambda link: lambda instance, user: link % (instance, user), '/instance/%s/user/%d')

    @staticmethod
    def getPageLinkImage(instance, user, target):
        assert isinstance(user, User)
        imageHtml = Display.getImage(user.profile_image_url, user.name, None, className='twitter-profile-image')

        return Display.getLink(UserInformationPage.link_info.getPageLink(instance,user.id), imageHtml, target=target)

    def __init__(self, application, userInformationWebSocketGroup):
        Display.__init__(self,
                         application,
                         pageRoute=('/instance/<instance>/user/<user:int>', None),
                         webSocketManagers=[userInformationWebSocketGroup],
                         onDisplayUsageFunc=onDisplayUsageFunc)

    @property
    def page_html_function(self):
        def func(templateArguments, instance, user):
            twitterInstance = self.application.twitter_instances.getInstanceByInstanceKey(instance)
            if twitterInstance is None:
                abort(404, "No active search stream found at this address")

            instanceDescription = getInstanceDescription(twitterInstance, True)
            instanceLink = getInstanceLink(twitterInstance)
            homeLink = getHomeLink(Configuration.PROJECT_NAME)

            templateArguments.update({'home_link' : homeLink,
                                      'instance' : instance,
                                      'instance_description' : instanceDescription,
                                      'instance_link' : instanceLink,
                                      'user_id' : user})
            return template('user.tpl', templateArguments)

        return func

class UserFollowerEnrichPage(Display):
    link_info = Display.LinkInfo(lambda link: lambda instance, user: link % (instance, user), '/instance/%s/user_follower_enrich/%d')

    def __init__(self, application, dataCollection, followerExtractorGateThread):
        Display.__init__(self,
                         application,
                         pageRoute=('/instance/<instance>/user_follower_enrich/<user:int>', None),
                         webSocketManagers=None,
                         onDisplayUsageFunc=onDisplayUsageFunc)
        assert isinstance(dataCollection, DataCollection)
        assert isinstance(followerExtractorGateThread, FollowerExtractorGateThread)

        self.data_collection = dataCollection
        self.follower_extractor_gate_thread = followerExtractorGateThread


    @property
    def page_html_function(self):
        def func(templateArguments, instance, user):
            try:
                twitterInstance = self.application.twitter_instances.getInstanceByInstanceKey(instance)
                if twitterInstance is None:
                    abort(404, "No active search stream found at this address")

                # We need name and followers count for the progress bar.
                userObject = self.data_collection.getUser(instance, user, twitterInstance.twitter_thread.twitter_session, False, UserProjection.Geocode(True, UserDataProjection(['name','followers_count'])))
                if not userObject:
                    abort(404, "No user found at this address")

                assert isinstance(userObject, User)
                if not self.follower_extractor_gate_thread.addUser(userObject, restrictInfluenceArea = False):
                    logger.warn('Not processed user: %s/%d for enrichment - shouldProcessUser returned false' % (instance,user))

            except KeyError:
                logger.warn('Follower information enrich request received for user which does not exist: %s/%d' % (instance, user))

            return redirect(UserInformationPage.link_info.getPageLink(instance, user))

        return func

class TwitterCachePage(Display):
    link_info = Display.LinkInfo(lambda link: lambda instance: link % instance, '/instance/%s/cached_tweets')

    PAGE_SIZE_ID_NAME_DATA = 80
    PAGE_SIZE_FULL_DATA = 10

    def __init__(self, application):
        Display.__init__(self,
                         application,
                         pageRoute=('/instance/<instance>/cached_tweets', None),
                         webSocketManagers=None,
                         onDisplayUsageFunc=onDisplayUsageFunc)

    @property
    def page_html_function(self):
        def func(templateArguments, instance):
            dataType = parseString(request.GET.type,['tweet','user'])
            start_epoch = parseInteger(request.GET.start_epoch)
            end_epoch = parseInteger(request.GET.end_epoch)
            page_num = parseInteger(request.GET.page)
            place_id = parseInteger(request.GET.place_id)
            provider_id = parseInteger(request.GET.provider_id)
            projection_type = parseString(request.GET.projection_type)
            followee = parseInteger(request.GET.followee)

            cache_id = GeocodeResultAbstract.buildCacheId(provider_id, place_id)

            if dataType is None:
                return redirect_problem('type is a required argument')

            if page_num is None:
                page_num = 0

            data = []
            if dataType == 'tweet':
                tweets = readTweetsFromCache(None, instance, cache_id, start_epoch, end_epoch, page_num, TwitterCachePage.PAGE_SIZE_FULL_DATA)
                if tweets is not None:
                    for tweet in tweets:
                        assert isinstance(tweet, Tweet)
                        userHtml = UserInformationPage.getPageLinkImage(instance, tweet.user, target='_self')

                        data.append([ tweet.created_at,
                                      userHtml,
                                      tweet.user.location_text,
                                      tweet.text ])

            elif dataType == 'user':
                if len(projection_type) == 0:
                    projection = None
                    pageSize = TwitterCachePage.PAGE_SIZE_FULL_DATA
                elif projection_type == 'name-only':
                    projection = UserProjection.IdNameImage()
                    pageSize = TwitterCachePage.PAGE_SIZE_ID_NAME_DATA
                else:
                    return redirect_problem('Unsupported projection type: %s' % projection_type)

                if followee is None:
                    return redirect_problem('Followee is required')

                users = readUsersFromCache(None, instance, cache_id, start_epoch, end_epoch, page_num, pageSize, followee, userProjection=projection)
                if users is not None:
                    for user in users:
                        assert isinstance(user, User)
                        data.append([user.id,
                                     user.name,
                                     user.profile_image_url,
                                     UserInformationPage.link_info.getPageLink(instance, user.id)])

            return {'json' : data}
        return func


class InfluenceCachePage(Display):
    link_info = Display.LinkInfo(lambda link: lambda instance: link % instance, '/instance/%s/influence')

    def __init__(self, application):
        Display.__init__(self,
                         application,
                         pageRoute=('/instance/<instance>/influence', None),
                         webSocketManagers=None,
                         onDisplayUsageFunc=onDisplayUsageFunc)

    @property
    def page_html_function(self):
        def func(templateArguments, instance):
            twitterInstance = self.application.twitter_instances.getInstanceByInstanceKey(instance)
            if twitterInstance is None:
                return dict()

            baseEpoch = twitterInstance.constructed_at

            start_epoch = parseInteger(request.GET.start_epoch, default=None)
            end_epoch = parseInteger(request.GET.end_epoch, default=None)
            source_place_id = parseInteger(request.GET.source_place_id)
            source_provider_id = parseInteger(request.GET.source_provider_id)

            if source_place_id is None:
                logger.error('Invalid place ID specified while providing influence data: %s' % unicode(source_place_id))
                return dict()

            source_cache_id = GeocodeResultAbstract.buildCacheId(source_provider_id, source_place_id)

            temporalCollection = getTemporalInfluenceCollection(instance)

            if start_epoch is not None:
                start_time_id = getTimeIdFromTimestamp(baseEpoch, Configuration.TEMPORAL_STEP, start_epoch)
            else:
                start_time_id = None

            if end_epoch is not None:
                end_time_id = getTimeIdFromTimestamp(baseEpoch, Configuration.TEMPORAL_STEP, end_epoch)
            else:
                end_time_id = None

            timerMs = getEpochMs()
            cacheData = getTemporalRange(temporalCollection, start_time_id, end_time_id, source_cache_id, preciseFromBack=True, preciseFromFront=True)
            logger.info('Took %dms to read temporal range data' % (getEpochMs() - timerMs))

            timerMs = getEpochMs()

            geocodeByPlaceType = dict()
            totalsByPlaceType = dict()

            if cacheData is not None:
                for providerId, providerIdData in cacheData.iteritems():
                    providerId = int(providerId)

                    for destination, count in providerIdData.iteritems():
                        split = destination.split('_')
                        placeType = int(split[0])
                        placeId = int(split[1])

                        record = [placeId,
                                  providerId,
                                  None,
                                  None,
                                  count,
                                  None]

                        geocodeByPlaceType.setdefault(placeType,list()).append(record)

                # Process only the records we are going to display.
                for placeType, records in geocodeByPlaceType.iteritems():
                    aux = sorted(records, key=lambda x: x[4], reverse=True)
                    aux = aux[:Configuration.DISPLAY_MAX_NUM_INFLUENCE_RECORDS_PER_PLACE_TYPE]
                    geocodeByPlaceType[placeType] = aux

                    for record in aux:
                        cacheId = GeocodeResultAbstract.buildCacheId(record[1], record[0])
                        geocode = geocodeFromCacheById(cacheId)

                        record[2] = geocode.display_name
                        record[3] = geocode.coordinate
                        count = record[4]
                        record[5] = geocode.bounding_box

                        totalsByPlaceType[placeType] = totalsByPlaceType.get(placeType,0) + count

            def getResultPart(placeType):
                return {'geocode_list' : geocodeByPlaceType.get(placeType,list()), 'total' : totalsByPlaceType.get(placeType, 0)}

            resultData = dict()
            resultData['city'] =        getResultPart(GeocodeResultAbstract.PlaceTypes.CITY)
            resultData['country'] =     getResultPart(GeocodeResultAbstract.PlaceTypes.COUNTRY)
            resultData['continent'] =   getResultPart(GeocodeResultAbstract.PlaceTypes.CONTINENT)

            logger.info('Took %dms to build temporal range result data' % (getEpochMs() - timerMs))

            return {'json' : resultData}
        return func



class GeocodeCachePage(Display):
    link_info = Display.LinkInfo(lambda link: lambda: link, '/geocode_search')

    def __init__(self, application, providerId):
        Display.__init__(self,
                         application,
                         pageRoute=('/geocode_search', None),
                         webSocketManagers=None)

        self.provider_id = providerId

    @property
    def page_html_function(self):
        def func(templateArguments):
            placeName = parseString(request.GET.place_name)

            data = list()

            if placeName is None:
                return {'json' : data}

            locations = list()
            maxLocations = 10

            locations += GeocodeResultAbstract.searchGnsByName(placeName,3)
            maxLocations -= len(locations)

            if maxLocations > 0:
                newLocations = geocodeSearch(self.provider_id,placeName,maxLocations)
                maxLocations -= len(newLocations)
                locations += newLocations


            for location in locations:
                assert isinstance(location,GeocodeResultAbstract)
                data.append((location.cache_id,location.bounding_box,location.coordinate,location.display_name))


            return {'json' : data}
        return func

class LandingPage(Display):
    link_info = Display.LinkInfo(lambda link: lambda: link, '/')

    def __init__(self, application):
        Display.__init__(self,
                         application,
                         pageRoute=('/', None),
                         webSocketManagers=None)

    @staticmethod
    def getLandingPageLink(pageNum):
        return Display.addArgumentsToLink(LandingPage.link_info.getPageLink(),page=pageNum)

    def getHumanTime(self, milliseconds):
        seconds = milliseconds / 1000
        if seconds < 60:
            if seconds == 1:
                return "1 second"

            return "%d seconds" % seconds

        minutes = seconds / 60
        if minutes < 60:
            if minutes == 1:
                return "1 minute"

            return "%d minutes" % minutes

        hours = minutes / 60
        if hours < 24:
            if hours == 1:
                return "1 hour"

            return "%d hours" % hours

        days = hours / 24
        if days == 1:
            return "1 day"

        return "%d days" % days

    @property
    def page_html_function(self):
        def func(templateArguments):
            argList = list()
            instanceList = self.application.twitter_instances.getInstanceList()

            # todo remove this, this generates more instances for debugging.
           # if len(instanceList) > 0:
            #    count = 0
            #    while count < 7:
            #        instanceList.append(instanceList[0])
            #        count += 1
            # todo end of remove this.

            numInstances = len(instanceList)

            numInstancesPerPage = Configuration.NUM_LANDING_PAGE_INSTANCES_PER_PAGE

            if numInstances > 3 or numInstances < 1:
                numInstancesPerRow = Configuration.NUM_LANDING_PAGE_INSTANCES_PER_ROW
            else:
                numInstancesPerRow = numInstances

            thumbnailSpan = 12 / numInstancesPerRow
            pageNum = parseInteger(request.GET.page,0,numInstances,0)
            startIndex = numInstancesPerPage * pageNum
            endIndex = startIndex + numInstancesPerPage
            numPages = int(ceil(float(numInstances) / float(numInstancesPerPage)))

            for instance in instanceList[startIndex:endIndex]:
                assert isinstance(instance, TwitterInstance)
                argList.append((LocationsMapPage.link_info.getPageLink(instance.instance_key),
                                instance.getShortDescription(True),
                                instance.geographic_setup_string))

            # Split into rows.
            argList = splitList(argList, numInstancesPerRow)
            templateArguments.update({'instances' : argList})

            # Pagination
            startSmallPageIndex = pageNum - 5
            endSmallPageIndex = 0
            if startSmallPageIndex < 0:
                endSmallPageIndex -= startSmallPageIndex
                startSmallPageIndex = 0

            endSmallPageIndex += (pageNum + 5)
            offEndBy = endSmallPageIndex - numPages
            if offEndBy > 0:
                startSmallPageIndex -= offEndBy
                if startSmallPageIndex < 0:
                    startSmallPageIndex = 0

                endSmallPageIndex = numPages

            pagination = list()
            for n in range(startSmallPageIndex, endSmallPageIndex):
                isCurrentPage = pageNum == n
                pagination.append((n+1,LandingPage.getLandingPageLink(n),isCurrentPage))

            step = (numPages - endSmallPageIndex) / 5
            if step > 0:
                for n in range(endSmallPageIndex,numPages,step):
                    pagination.append((n+1,LandingPage.getLandingPageLink(n),False))

            if pageNum < numPages - 1:
                templateArguments.update({'pagination_next' : LandingPage.getLandingPageLink(pageNum + 1)})

            if pageNum > 0:
                templateArguments.update({'pagination_previous' : LandingPage.getLandingPageLink(pageNum - 1)})

            maxInactiveTime = Configuration.MAX_INSTANCE_INACTIVE_TIME_MS
            maxTotalTime = Configuration.MAX_INSTANCE_TOTAL_AGE_MS

            templateArguments.update({'pagination' : pagination,
                                      'thumbnail_span' : thumbnailSpan,
                                      'build_instance_link' : OAuthSignIn.link_info.getPageLink(),
                                      'maxInactiveTime' : self.getHumanTime(maxInactiveTime),
                                      'maxTotalTime' : self.getHumanTime(maxTotalTime)})

            return template('landing-page.tpl',templateArguments)
        return func

class LocationsPage(Display):
    link_info = Display.LinkInfo(lambda link: lambda instance, location, providerId: link % (instance, location, providerId) , '/instance/%s/location/%d/%d/page')

    def __init__(self, application, tweetByLocationWebSocketGroup, dataDownloadWebSocketManager, realtimePerformance):
        Display.__init__(self,
                         application,
                         pageRoute=('/instance/<instance>/location/<location:int>/<provider:int>/page', None),
                         webSocketManagers=[tweetByLocationWebSocketGroup,
                                            (dataDownloadWebSocketManager, False),
                                            (realtimePerformance, False)],
                         onDisplayUsageFunc=onDisplayUsageFunc)

    @property
    def page_html_function(self):
        def func(templateArguments, instance, location, provider):
            twitterInstance = self.application.twitter_instances.getInstanceByInstanceKey(instance)
            if twitterInstance is None:
                abort(404, "No active search stream found at this address")

            geocode = geocodeFromCacheById(GeocodeResultAbstract.buildCacheId(provider,location))
            assert geocode is not None

            instanceDescription = getInstanceDescription(twitterInstance)
            instanceLink = getInstanceLink(twitterInstance)

            homeLink = getHomeLink(Configuration.PROJECT_NAME)

            templateArguments.update({'home_link' : homeLink,
                                      'instance' : instance,
                                      'location' : location,
                                      'provider' : provider,
                                      'instance_link' : instanceLink,
                                      'instance_description' : instanceDescription,
                                      'place' : geocode.display_name_short,
                                      'place_coord' : geocode.coordinate,
                                      'startEpoch' : twitterInstance.constructed_at,
                                      'server_current_epoch' : getEpochMs(),
                                      'max_tweets' : Configuration.MAX_CLIENT_LIVE_TWEETS}) # Client needs to offset to this epoch in case its clock is wrong.

            if geocode.has_bounding_box:
                templateArguments.update({'place_bounding_box' : geocode.bounding_box})

            if geocode.has_country:
                templateArguments.update({'place_country_link' : LocationsPage.link_info.getPageLink(instance, geocode.country.place_id, geocode.country.provider_id)})
                templateArguments.update({'place_country' : geocode.country.display_name_short})

            if geocode.has_continent:
                templateArguments.update({'place_continent_link' : LocationsPage.link_info.getPageLink(instance, geocode.continent.place_id, geocode.continent.provider_id)})
                templateArguments.update({'place_continent' : geocode.continent.display_name_short})

            return template('location.tpl', templateArguments)

        return func


class BulkDownloadDataProvider(AsyncTunnelProviderFile):
    link_info = Display.LinkInfo(lambda link: lambda instanceId, socketId, tunnelId: link % (instanceId, socketId, tunnelId) , '/instance/%s/bulk_download_provider/%d/%s')

    def __init__(self, application):
        super(BulkDownloadDataProvider,self).__init__(application,
                                                      pageRoute=('/instance/<instance>/bulk_download_provider/<socket_id:int>/<tunnel_id>',None),
                                                      onDisplayUsageFunc=onDisplayUsageFunc)

    def getFileName(self, tunnelId):
        if tunnelId == 'tweet_tunnel':
            return 'Tweets_' + getDateTime()
        else:
            return 'Users_' + getDateTime()

    def getFileExtension(self, tunnelId):
        return 'csv'