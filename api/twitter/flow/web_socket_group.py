import copy
import json
import logging
from bottle import request
import gevent
from api.caching.tweet_user import UserProjection, readUsersFromCache, readTweetsFromCache, NoQueryProjection
from api.core.signals.events import EventSignaler
from api.core.utility import Timer, parseInteger, parseBoolean, getPercentage, getEpochMs, parseString
from api.geocode.geocode_shared import GeocodeResultAbstract, GeocodeResultGNS
from api.twitter.feed import User, Tweet, UserFollowerEnrichmentProgress, Place, UserAnalysisFollowersGeocoded
from api.twitter.flow.data_converter import getUserRepresentation, getUserHeader, getTweetHeader, getTweetRepresentation
from api.twitter.flow.data_core import DataCollection, RealtimePerformance
from api.twitter.flow.display import UserInformationPage, UserFollowerEnrichPage, LocationsPage
from api.twitter.flow.display_core import Display
from api.twitter.flow.web_socket_group_core import GenericMultiDataWsgInstanceBased, GenericWsg, WebSocketManagerDataProvider, GenericWsgInstanced
from api.web.web_core import WebApplicationTwitter
from api.web.web_socket import MapControl, DivControl, DocumentControl
from api.web.web_utility import SignalActions

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class RealtimePerformanceWsg(GenericWsg):
    def __init__(self, application, realtimePerformanceSignaler, route=None):
        if route is None:
            route = ('/instance/<instance>/realtime_performance', '/instance/%s/realtime_performance')

        super(RealtimePerformanceWsg, self).__init__(key='realtime_performance',
                                                     route=route,
                                                     signalers=[realtimePerformanceSignaler],
                                                     application=application)

    def getControl(self):
        return DocumentControl('document')

    def extractDataFromSignal(self, signalData):
        return signalData

    def extractItemFromData(self, data, signalerKey):
        if signalerKey.provider_id is not None and signalerKey.place_id is not None:
            data = data['location_tweets']
            locationCacheId = GeocodeResultAbstract.buildCacheIdTuple(signalerKey.provider_id, signalerKey.place_id)
        else:
            data = data['instance_tweets']
            locationCacheId = None

        aux = data.get(signalerKey.instance)
        if aux is None:
            return None

        if locationCacheId is not None:
            aux = aux.get(locationCacheId)
            if aux is None:
                return None

        aux = aux.get('success',None)

        if aux is not None:
            assert isinstance(aux, RealtimePerformance)
            tweetsPerDay, tweetsPerDayUpdated = aux.tweets_per_day.time_period_count_updated(True,True,True)
            tweetsPerHour, tweetsPerHourUpdated = aux.tweets_per_hour.time_period_count_updated(True,True,True)
            tweetsPerMinute, tweetsPerMinuteUpdated = aux.tweets_per_minute.time_period_count_updated(True,True,True)
        else:
            tweetsPerDayUpdated = tweetsPerHourUpdated = tweetsPerMinuteUpdated = False
            tweetsPerDay = tweetsPerHour = tweetsPerMinute = None

        aux = data.get(signalerKey.instance)
        aux = aux.get('geocode_fail')
        if aux is not None:
            assert isinstance(aux, RealtimePerformance)
            failGeocodeTweetsPerDay, failGeocodeTweetsPerDayUpdated = aux.tweets_per_day.time_period_count_updated(True,True,True)
            failGeocodeTweetsPerHour, failGeocodeTweetsPerHourUpdated = aux.tweets_per_hour.time_period_count_updated(True,True,True)
            failGeocodeTweetsPerMinute, failGeocodeTweetsPerMinuteUpdated = aux.tweets_per_minute.time_period_count_updated(True,True,True)
        else:
            failGeocodeTweetsPerDayUpdated = failGeocodeTweetsPerHourUpdated = failGeocodeTweetsPerMinuteUpdated = False
            failGeocodeTweetsPerDay = failGeocodeTweetsPerHour = failGeocodeTweetsPerMinute = None

        if tweetsPerDayUpdated is tweetsPerHourUpdated is tweetsPerMinuteUpdated is \
           failGeocodeTweetsPerDayUpdated is failGeocodeTweetsPerHourUpdated is failGeocodeTweetsPerMinuteUpdated is False:
            newData = False
        else:
            newData = True

        if tweetsPerMinute is None:
            tweetsPerSecond = None
        else:
            tweetsPerSecond = int(tweetsPerMinute / 60)
            if tweetsPerHour is None:
                tweetsPerHour = tweetsPerMinute * 60

        if tweetsPerDay is None and tweetsPerHour is not None:
            tweetsPerDay = tweetsPerHour * 24

        if failGeocodeTweetsPerMinute is None:
            failGeocodeTweetsPerSecond = None
        else:
            failGeocodeTweetsPerSecond = int(failGeocodeTweetsPerMinute / 60)
            if failGeocodeTweetsPerHour is None:
                failGeocodeTweetsPerHour = failGeocodeTweetsPerMinute * 60

        if failGeocodeTweetsPerDay is None and failGeocodeTweetsPerHour is not None:
            failGeocodeTweetsPerDay = failGeocodeTweetsPerHour * 24

        if tweetsPerSecond < 1 and tweetsPerDay > 0:
            tweetsPerSecond = '< 1'

        if tweetsPerMinute < 1 and tweetsPerDay > 0:
            tweetsPerMinute = '< 1'

        if tweetsPerHour < 1 and tweetsPerDay > 0:
            tweetsPerHour = '< 1'

        return newData, json.dumps([[tweetsPerSecond,                    tweetsPerMinute,                    tweetsPerHour,                  tweetsPerDay],
                                    [failGeocodeTweetsPerSecond,         failGeocodeTweetsPerMinute,         failGeocodeTweetsPerHour,       failGeocodeTweetsPerDay]])

    @property
    def isCacheValueEnabled(self):
        return False

    def pushSocketDisplayChange(self, controls, updatedItem, oldCachedValue, isInitialPush, signaler, signalerKey):
        control = controls['document']
        newData, data = updatedItem

        if newData or isInitialPush:
            assert isinstance(control, DocumentControl)
            control.executeJavascript('onStatistics(\'%s\');' % unicode(data))

    def getArguments(self):
        providerId          =        parseInteger(request.GET.provider_id)
        placeId             =        parseInteger(request.GET.place_id)
        return {'provider_id' : providerId, 'place_id' : placeId}

class LocationMapWsg(GenericMultiDataWsgInstanceBased):
    def __init__(self, application, locations, route=None):
        if route is None:
            route = ('/instance/<instance>/map/websocket', '/instance/%s/map/websocket')

        super(LocationMapWsg, self).__init__(key='LocationMapWsg', route=route, signalers=[locations],
            application=application)

    def getControl(self):
        return MapControl('map')

    def pushSocketDisplayChangeEx(self, controls, newItems, removedItems, isInitialPush, signalerKey):
        control = controls['map']
        instance = signalerKey[0]

        if newItems is not None:
            for item in newItems:
                assert isinstance(item, GeocodeResultAbstract)

                popupText = Display.getLink(LocationsPage.link_info.getPageLink(instance, item.place_id, item.provider_id), '<b>%s</b>' % unicode(item.display_name), target='_self')

                placeType = item.place_type
                customLayers = []
                if placeType == GeocodeResultAbstract.PlaceTypes.CITY:
                    customLayers.append('city')
                elif placeType == GeocodeResultAbstract.PlaceTypes.COUNTRY:
                    customLayers.append('country')
                elif placeType == GeocodeResultAbstract.PlaceTypes.CONTINENT:
                    customLayers.append('continent')
                else:
                    logger.error('Unsupported place type received by location map web socket group: %s' % unicode(placeType))
                    continue

                properties = {'custom_layers' : customLayers}
                control.addMarker(coord=item.coordinate, popupText=popupText, hashKey=item, properties=properties)

    def extractDataFromSignal(self, signalData):
        return signalData['tweets_by_location']['data']

    def continueExtractItemFromData(self, data, instanceData, signalerKey):
        return set(instanceData.keys())


class TweetsByLocationWsg(GenericMultiDataWsgInstanceBased):
    def __init__(self, application, signaler, route=None):
        if route is None:
            route = (
                '/instance/<instance>/location/<location:int>/<provider:int>/tweet/websocket',
                '/instance/%s/location/%d/%d/tweet/websocket')
        super(TweetsByLocationWsg, self).__init__('TweetsByLocationWsg', application, [signaler], route)

    def getControl(self):
        control = DivControl(self.key)
        control.has_set_title = False
        return control

    @property
    def isCacheValueEnabled(self):
        return True

    def pushSocketDisplayChangeEx(self, controls, addedItems, removedItems, isInitialPush, signalerKey):
        control = controls[self.key]

        # Without caching we do not do comparisons with previous data.
        # We deal with only new items.
        assert isinstance(control, DivControl)
        instance = signalerKey[0]

        # Most recent first.
        addedItems = sorted(addedItems,key=lambda x: x.timestamp)

        if isInitialPush:
            wrap = ['b']
            control.setHeader([control.getCell('Created','span2', wrap),
                               control.getCell('User','span1', wrap),
                               control.getCell('Location','span2', wrap),
                               control.getCell('Status','span7', wrap)])

        for tweet in addedItems:
            assert isinstance(tweet, Tweet)

            userHtml = UserInformationPage.getPageLinkImage(tweet.instance_key, tweet.user, target='_self')

            cells = [control.getCell(tweet.created_at,'span2',wrapIn=[]),
                     control.getCell(userHtml,'span1',wrapIn=[]),
                     control.getCell(tweet.user.location_text,'span2',wrapIn=[]),
                     control.getCell(tweet.text,'span7',wrapIn=[])]

            control.addRow(hash(tweet), cells, rowIndex=0)

    def extractDataFromSignal(self, signalData):
        return signalData['tweets_by_location']['data']

    def continueExtractItemFromData(self, data, instanceData, signalerKey):
        location = signalerKey.location
        providerId = signalerKey.provider

        tup = GeocodeResultAbstract.buildCacheIdTuple(providerId,location)
        return set(instanceData.get(tup, dict()).keys())


def getFollowersInfoDiv(divControl, analysis, mapSpan, textSpan, contentsWrap = None, headerWrap = None):
    assert isinstance(analysis, UserAnalysisFollowersGeocoded)

    followerLocationsHtmlHeader = divControl.getRowHtml([divControl.getCellHtml('Location',wrapIn=headerWrap,className='span6'),
                                                         divControl.getCellHtml('# of users',wrapIn=headerWrap,className='span2'),
                                                         divControl.getCellHtml('% of all users',wrapIn=headerWrap,className='span2'),
                                                         divControl.getCellHtml('% of geo-coded users',wrapIn=headerWrap,className='span2')])
    followerLocationsHtmlContents = ''

    totalNumFollowers = analysis.num_followers
    totalNumGeocodedFollowers = analysis.num_geocoded_followers
    results = analysis.results

    for location, numFollowers in results:
        assert isinstance(location, GeocodeResultAbstract)
        locationName = unicode(location.display_name)

        try:
            placeHtml = '<a href="#" title="Pan map to %s" onclick="panMapTo([%s,%s]); return false;">%s</a>' % (locationName, location.coordinate[0], location.coordinate[1], locationName)
            isGeocoded = True
        except NotImplementedError:
            placeHtml = locationName
            isGeocoded = False


        percentage = float(numFollowers) / float(totalNumFollowers) * 100

        if isGeocoded:
            percentageGeocoded = float(numFollowers) / float(totalNumGeocodedFollowers) * 100
            percentageGeocoded = '%.1f' % percentageGeocoded
        else:
            percentageGeocoded = 'N/A'

        followerLocationsHtmlContents += divControl.getRowHtml([divControl.getCellHtml(placeHtml,                       wrapIn=contentsWrap, className='span6 followers-div-geocode-text-contents-cell'),
                                                                divControl.getCellHtml('%d' % numFollowers,             wrapIn=contentsWrap, className='span2 followers-div-geocode-text-contents-cell'),
                                                                divControl.getCellHtml('%.1f' % percentage,             wrapIn=contentsWrap, className='span2 followers-div-geocode-text-contents-cell'),
                                                                divControl.getCellHtml(percentageGeocoded,     wrapIn=contentsWrap, className='span2 followers-div-geocode-text-contents-cell')],
                                                               rowClass='row-fluid followers-div-geocode-text-contents-row')

    mapCell = divControl.getContainerHtml(divControl.getCellHtml(cellContents='',className="followers-div-geocode-map",wrapIn=[],id='UserWsg_follower_map'),className='span%d pull-right' % mapSpan)

    textCellHeader =   divControl.getCellHtml(cellContents=followerLocationsHtmlHeader,className='span12 scroll-padding followers-div-geocode-text-header', wrapIn=[], id = 'follower_location_table_header')
    textCellContents = divControl.getCellHtml(cellContents=followerLocationsHtmlContents,className='span12 scrollable followers-div-geocode-text-contents', wrapIn=[], id = 'follower_location_table')
    textCell = divControl.getContainerHtml(divControl.getRowHtml([textCellHeader]) + divControl.getRowHtml([textCellContents]), className = 'span%d pull-left followers-div-geocode-text' % textSpan)
    return divControl.getContainerHtml(divControl.getRowHtml([textCell,mapCell]),className='span12')


class UserWsg(GenericWsgInstanced, GenericWsg):
    def __init__(self, application, dataCollection, signaler, route=None):
        if route is None:
            route = ('/instance/<instance>/user/<user:int>/websocket', '/instance/%s/user/%d/websocket')

        super(UserWsg, self).__init__('UserWsg', application, [signaler], route)

        assert isinstance(dataCollection, DataCollection)
        assert isinstance(self.application, WebApplicationTwitter)

        self.data_collection = dataCollection

    def getControls(self):
        theList = [DivControl('UserWsg_div'), MapControl('UserWsg_follower_map')]

        mainControl = theList[0]
        mainControl.pushed_enriched_follower_information = False
        mainControl.last_follower_information_enrich_draw = -1
        return theList

    def getInitialItem(self, signaler, key):
        instanceId = key[0]
        userId = key[1]

        twitterInstance = self.application.twitter_instances.getInstanceByInstanceKey(instanceId)
        if twitterInstance is None:
            return None

        user = self.data_collection.getUser(instanceId, userId, twitterInstance.twitter_thread.twitter_session, False, UserProjection.ExcludeRecursiveData())

        return user

    def isGroupCacheEnabled(self):
        return False

    def extractDataFromSignal(self, signalData):
        return signalData

    def preprocessSignal(self, signaler, previousSignalData, newSignalData):
        if previousSignalData is None:
            previousSignalData = dict()

        newItem = newSignalData['all_users']['data']
        previousItem = previousSignalData.get(newItem.id,None)

        if previousItem is None:
            previousSignalData[newItem.id] = newItem
        else:
            previousItem.merge(newItem)

        return previousSignalData

    def continueExtractItemFromData(self, data, instanceData, signalerKey):
        userId = signalerKey[1]

        if userId in data:
            return data[userId]
        else:
            return None

    def getComparisonValueFromCacheValue(self, cacheValue):
        assert isinstance(cacheValue, User)
        return cacheValue.timestamp

    def extractCacheValueFromItem(self, value):
        assert isinstance(value, User)
        return copy.copy(value)

    def updateItemFromCacheValue(self, newItem, oldCacheValue):
        assert isinstance(newItem, User)
        if oldCacheValue is None:
            newItem.merge_result = None
            return newItem

        assert isinstance(oldCacheValue, User)
        result = oldCacheValue.merge(newItem)
        oldCacheValue.merge_result = result
        return oldCacheValue

    def pushSocketDisplayChange(self, controls, updatedItem, oldCachedValue, isInitialPush, signaler, signalerKey):
        divControl = controls['UserWsg_div']
        followerMapControl = controls['UserWsg_follower_map']

        assert isinstance(divControl, DivControl)
        assert isinstance(followerMapControl, MapControl)

        instance = signalerKey[0]
        user = signalerKey[1]

        queueProgressBarId =  'follower-enrichment-queue-progress-bar'
        userProgressBarId =   'follower-enrichment-user-progress-bar'
        userIdProgressBarId = 'follower-enrichment-userId-progress-bar'
        descriptionId =       'follower-enrichment-progress-description'

        assert isinstance(updatedItem, User)

        # Utility functions for updating main page.
        def getHeaderCell(text, headerWidth=2):
            return divControl.getCell(text, 'span%d vertical-header' % headerWidth, ['b'])

        def getContentsCell(text, contentsWidth=10):
            return divControl.getCell(text,'span%d vertical-content' % contentsWidth, [])

        hashKeyTracker = [1]
        def updateRow(header, contents, theKey=hashKeyTracker):
            if contents is None:
                contents = '-'

            isHeader = header is not None
            if isHeader:
                headerWidth = 2
                contentsWidth = 10
            else:
                headerWidth = 0
                contentsWidth = 12

            text = [getContentsCell(contents, contentsWidth)]
            if isHeader:
                text = [getHeaderCell(header, headerWidth)] + text

            divControl.updateRow(theKey[0], text, rowIndex = -1, rowClass = 'row-fluid vertical-row')

            if theKey is not None:
                theKey[0] += 1

        numberOfFollowers = updatedItem.num_followers

        # Does what it says on the tin.
        def updateFollowerInformationEnrichedStatus():
            if (not updatedItem.is_followers_loaded) and updatedItem.queued_for_follower_enrichment:
                progressBarHtml = '<div class="progress progress-striped active">'\
                                  '<div class="bar bar-danger" id="%s" style="width: %.2f%%"></div>'\
                                  '<div class="bar bar-warning" id="%s" style="width: %.2f%%"></div>'\
                                  '<div class="bar bar-success" id="%s" style="width: %.2f%%"></div></div>' % (queueProgressBarId, updatedItem.follower_enrichment_progress.queue_progress,
                                                                                                               userProgressBarId ,updatedItem.follower_enrichment_progress.user_progress,
                                                                                                               userIdProgressBarId, updatedItem.follower_enrichment_progress.user_id_progress)

                followerInformationEnrichedValue = '<br><br><div class="text-info" id="%s">%s</div>%s' % (descriptionId,
                                                                                                  formatDescriptionWithUserLink(updatedItem.follower_enrichment_progress.enrichment_progress_description, updatedItem.follower_enrichment_progress.queue_waiting_for_user),
                                                                                                  progressBarHtml)
                returnVal = 1
            elif (not updatedItem.is_followers_loaded) and updatedItem.last_follower_enrichment_error:
                followerInformationEnrichedValue = ' - failed to enrich followers with reason: %s' % updatedItem.last_follower_enrichment_error
                returnVal = 2
            elif (not updatedItem.is_followers_loaded) and (not updatedItem.queued_for_follower_enrichment) and updatedItem.is_geocoded:
                linkToFollow = UserFollowerEnrichPage.link_info.getPageLink(instance, user)
                link = '<br><br>%s<br>' % Display.getLink('#','Get Followers','_self','$(this).addClass(\'disabled\'); getPage(\'%s\', null, null, null); return false;' % linkToFollow, htmlClass='btn btn-success get-followers-button')
                followerInformationEnrichedValue = link
                returnVal = 4
            elif not updatedItem.is_geocoded:
                followerInformationEnrichedValue = ' - not geocoded so cannot enrich followers'
                returnVal = 3
            else:
                followerInformationEnrichedValue = ''
                returnVal = 0

            if divControl.last_follower_information_enrich_draw != returnVal or returnVal == 2:
                displayValue = '%d followers%s' % (numberOfFollowers, followerInformationEnrichedValue)

                updateRow('Follower Information', displayValue, [1000])
                divControl.last_follower_information_enrich_draw = returnVal

            return returnVal

        # Generates the progress bar description.
        def formatDescriptionWithUserLink(description, user):
            if user is not None:
                link = Display.getLink(UserInformationPage.link_info.getPageLink(user.instance_key, user.id), unicode(user.name), target='_self')
                return description % link
            else:
                return description

        # Handles progress bar changes, updating the enrichment value if necessary in order
        # to initialize the progress bar.
        def handleProgressBarChanges(progress, mergeResult):
            assert isinstance(progress, UserFollowerEnrichmentProgress)

            if isInitialPush:
                mergeResult = 1,1,1 # update all progress bars.

            if mergeResult is None:
                return

            difQueueProgress, difUserIdProgress, difUserProgress = mergeResult
            if difQueueProgress == 0 and difUserIdProgress == 0 and difUserProgress == 0:
                return

            # Not initialized yet or enrichment complete.
            if divControl.last_follower_information_enrich_draw != 1:
                return

            def doProgressBarChange(progressBarId, percentage):
                divControl.executeJavascript('document.getElementById("%s").style.width="%.2f%%";' % (progressBarId, percentage))

            def setDescription(description):
                divControl.executeJavascript('document.getElementById("%s").innerHTML=\'%s\';' % (descriptionId, description))

            if difUserProgress > 0:
                doProgressBarChange(userProgressBarId, progress.user_progress)

            if difUserIdProgress > 0:
                doProgressBarChange(userIdProgressBarId, progress.user_id_progress)

            if difQueueProgress > 0:
                doProgressBarChange(queueProgressBarId, progress.queue_progress)

            description = formatDescriptionWithUserLink(progress.enrichment_progress_description, progress.queue_waiting_for_user)
            setDescription(description)

        # Populate contents of page.
        updateRow('Timestamp', updatedItem.date_time)
        updateRow('User name', updatedItem.name)
        updateRow('Profile Image', Display.getImage(updatedItem.profile_image_url, updatedItem.name, className = 'twitter-profile-image'))
        updateRow('Description', updatedItem.description)
        updateRow('Location', updatedItem.location_text)

        if updatedItem.has_twitter_place:
            place = updatedItem.twitter_place
            assert isinstance(place, Place)
            placeCountry = '%s/%s' % (place.country, place.country_code)
            placeName = place.full_name

            placeNameContents = 'Place: %s' % placeName
            if placeCountry is not None:
                placeNameContents += ' / Country: %s' % placeCountry
        else:
            placeNameContents = '-'

        updateRow('Twitter Place', placeNameContents)

        geocoded_location = None

        if updatedItem.is_geocoded:
            raw_location = updatedItem.location_geocode
            assert isinstance(raw_location, GeocodeResultAbstract)
            geocoded_location = Display.getLink(LocationsPage.link_info.getPageLink(instance,
                                                                                    updatedItem.location_geocode.place_id,
                                                                                    updatedItem.location_geocode.provider_id),
                                                                                    updatedItem.location_geocode.display_name_short,
                                                                                    target='_self')

            if raw_location.has_country:
                countryGeocode = raw_location.country
                assert isinstance(countryGeocode, GeocodeResultGNS)

                countryHtml = Display.getLink(LocationsPage.link_info.getPageLink(instance,
                                                                                  countryGeocode.place_id,
                                                                                  countryGeocode.provider_id),
                                              countryGeocode.display_name,
                                              target='_self')
                geocoded_location = '%s / %s' % (geocoded_location, countryHtml)

            if raw_location.has_continent:
                continentGeocode = raw_location.continent
                assert isinstance(continentGeocode, GeocodeResultGNS)

                continentHtml = Display.getLink(LocationsPage.link_info.getPageLink(instance,
                                                                                  continentGeocode.place_id,
                                                                                  continentGeocode.provider_id),
                                                continentGeocode.display_name,
                                                target='_self')
                geocoded_location = '%s / %s' % (geocoded_location, continentHtml)

        updateRow('Geocoded Location', geocoded_location)

        #geocodedFrom = updatedItem.geocoded_from
        #if geocodedFrom is None:
         #   geocodedFrom = '-'
        #updateRow('Geocoded From', geocodedFrom)

        divControl.executeJavascript('setPageTitle("%s");' % updatedItem.name)

        updateFollowerInformationEnrichedStatus()
        handleProgressBarChanges(updatedItem.follower_enrichment_progress, updatedItem.merge_result)

        if updatedItem.is_followers_loaded and not updatedItem.queued_for_follower_enrichment:
            # Don't update enriched follower information needlessly (say only timestamp changes).
            # If we update the map it resets it which is a problem.
            if not divControl.pushed_enriched_follower_information:
                divControl.pushed_enriched_follower_information = True

                updateRow(None, divControl.getContainerHtml('', 'span12', 'followers-list'))
                divControl.executeJavascript('setupFollowersList();')

                sortedResults = []
                analyser = updatedItem.analysers[UserAnalysisFollowersGeocoded.analysis_name_static()]
                assert isinstance(analyser, UserAnalysisFollowersGeocoded)

                updateRow(None, getFollowersInfoDiv(divControl, analyser, 6, 6, [], ['b']))
                divControl.executeJavascript('applyScrollbars();')

                divControl.executeJavascript('setupFollowerLocationMap();')
                for location, numFollowers in analyser.num_geocoded_followers_by_location.iteritems():
                    assert isinstance(location,GeocodeResultAbstract)

                    percentage = float(numFollowers) / analyser.num_geocoded_followers * 100

                    popupText = location.display_name
                    followerMapControl.addMarker(location.coordinate,
                                                 popupText=popupText,
                                                 properties={'percentage' : percentage})


class BulkDownloadDataWsg(WebSocketManagerDataProvider):
    def __init__(self, application, route=None, bulkDownloadDataProvider=None):
        if route is None:
            route = (
                '/instance/<instance>/bulk_download/websocket',
                '/instance/%s/bulk_download/websocket')
        super(BulkDownloadDataWsg, self).__init__('BulkDownloadDataWsg', route, application, bulkDownloadDataProvider)


    def getControl(self):
        return DocumentControl(self.key)

    def initialiseTunnelSlots(self, webSocket):
        self.initialiseTunnelSlot('user_tunnel', webSocket)
        self.initialiseTunnelSlot('tweet_tunnel', webSocket)

    def onSocketId(self, webSocket, socketId, tupleArguments):
        instanceId = tupleArguments.instance

        mainControl = webSocket.controls[self.key]
        mainControl.executeJavascript('setSocketId("%s", "%d");' % (unicode(instanceId), socketId))

    @property
    def requireAllTunnelsOpen(self):
        return False

    def manageSocket(self, webSocket, tupleArguments, socketId):
        instanceId = tupleArguments[0]

        mainControl = webSocket.controls[self.key]
        assert isinstance(mainControl, DocumentControl)

        bytesPerBatch       =        parseInteger(request.GET.batchSizeBytes, maximum=1024 * 1024 * 256, default=1024 * 1024 * 1)
        tweetInfo           =        parseBoolean(request.GET.tweet_info, False)
        followerInfo        =        parseBoolean(request.GET.follower_info_full, False)
        followerInfoShort   =        parseBoolean(request.GET.follower_info_short, False)
        providerId          =        parseInteger(request.GET.provider_id)
        placeId             =        parseInteger(request.GET.place_id)
        startEpoch          =        parseInteger(request.GET.start_epoch)
        endEpoch            =        parseInteger(request.GET.end_epoch)

        if placeId is not None and providerId is not None:
            placeCacheId = GeocodeResultAbstract.buildCacheId(providerId, placeId)
        else:
            placeCacheId = None

        if followerInfo:
            tweetInfo = False
            followerInfoShort = False
        elif tweetInfo:
            followerInfo = False
            followerInfoShort = False
        elif followerInfoShort:
            followerInfo = False
            tweetInfo = False
        else:
            followerInfo = True


        userTunnelId = 'user_tunnel'
        tweetTunnelId = None

        if tweetInfo:
            tweetTunnelId = 'tweet_tunnel'

        def openRequiredTunnels():
            if tweetInfo:
                return self.openTunnels(webSocket)
            else:
                return self.openTunnel(userTunnelId, webSocket)

        if not openRequiredTunnels():
            logger.error('Failed to open initial tunnels')
            return False

        if tweetInfo:
            followerIdsFlag = False
            followeeIdsFlag = False
            analysisFlag = False
            isFollowersLoadedRequirement = None
            associatedWithTweetRequirement = True
            recursiveCacheFlag = False
            followerIdsProjection = None
            outputType = 1 # for csv.
        elif followerInfo:
            followerIdsFlag = True
            followeeIdsFlag = True
            analysisFlag = True
            isFollowersLoadedRequirement = True
            associatedWithTweetRequirement = None
            recursiveCacheFlag = True
            followerIdsProjection = None # this gives us all data on each follower.
            outputType = 2
        elif followerInfoShort:
            followerIdsFlag = True
            followeeIdsFlag = True
            followerIdsProjection = NoQueryProjection()
            analysisFlag = True
            isFollowersLoadedRequirement = True
            associatedWithTweetRequirement = None
            recursiveCacheFlag = True
            outputType = 3
        else:
            raise NotImplementedError()

        userProjection = UserProjection(True,
                                        True,
                                        None,
                                        True,
                                        followerIdsFlag,
                                        followerIdsProjection,
                                        followeeIdsFlag,
                                        UserProjection.Id(),
                                        True,
                                        False,
                                        False,
                                        True,
                                        True,
                                        False,
                                        False,
                                        False,
                                        False,
                                        analysisFlag)

        isFirstIteration = [True]

        twitterInstance = self.application.twitter_instances.getInstanceByInstanceKey(instanceId)
        if twitterInstance is None:
            return False

        twitterSession = twitterInstance.twitter_thread.twitter_session
        progressBarTotalId = 'progress-bar-total'
        progressBarCurrentBatchId = 'progress-bar-current-batch'

        signaler = EventSignaler(self.key, [webSocket])

        updateProgressBarFreq = Timer(400,True)

        def sendData(tunnelId, data):
            self.sendDataOnTunnel(webSocket, tunnelId, (unicode(data) + '\r\n'))

        def sendHeader():
            sendData(userTunnelId, getUserHeader(outputType))

            if tweetTunnelId is not None:
                sendData(tweetTunnelId, getTweetHeader())

        def doProgressBarChange(percentage, progressBarId):
            mainControl.executeJavascript('$("#%s").width("%.3f%%");' % (progressBarId, percentage))

        sendHeader()

        counter = [0]
        previousCounter = [0]
        def updateSocket(controls,
                         data,
                         bytesCounter=counter,
                         bytesPerBatch=bytesPerBatch,
                         previousCounter=previousCounter,
                         isFirstIteration=isFirstIteration):
            user = data['user_data']
            tweet = data['tweet_data']
            percentage = data['percentage']
            isFinished = data['isFinished']

            control = controls[self.key]
            assert isinstance(control, DocumentControl)

            def updateProgressBars():
                previousCounter[0] = thisCounter = bytesCounter[0]

                percentageCurrentBatch = float(thisCounter) / float(bytesPerBatch) * 100
                percentageTotal = percentage

                if percentageTotal >= 100:
                    percentageCurrentBatch = 100

                if isFirstIteration[0] and percentageCurrentBatch < percentageTotal:
                    percentageCurrentBatch = percentageTotal

                doProgressBarChange(percentageTotal, progressBarTotalId)
                doProgressBarChange(percentageCurrentBatch, progressBarCurrentBatchId)

            if previousCounter[0] != bytesCounter[0] and updateProgressBarFreq.ticked():
                updateProgressBars()

            dataToSendToClient = ''
            if user is not None:
                assert isinstance(user,User)
                dataToSendToClient = getUserRepresentation(user, outputType)
                sendData(userTunnelId, dataToSendToClient)

            if tweet is not None:
                assert isinstance(tweet, Tweet)
                dataToSendToClient = getTweetRepresentation(tweet)
                sendData(tweetTunnelId, dataToSendToClient)

            dataLength = len(dataToSendToClient)
            bytesCounter[0] += dataLength

            if bytesCounter[0] > bytesPerBatch or isFinished:
                updateProgressBars()
                isFirstIteration[0] = False

                bytesCounter[0] = 0
                mainControl.executeJavascript('onBatchEnd();')

                self.closeTunnels(webSocket)

                if not isFinished:
                    logger.debug('Waiting to receive next data provider')
                    if not openRequiredTunnels():
                        logger.warning('Failed to reinitialize tunnel slots')
                        webSocket.cleanup()
                        return

                    sendHeader()
                else:
                    mainControl.executeJavascript('onFinished();')

                    webSocket.cleanup()

        def onCacheIteration(iteration, total, isFinished, data, iteratorId):
            # Don't write followee data to output as it would duplicate alot of data.
            if iteratorId == 'followee':
                data = None

            running = not webSocket.is_cleaned_up
            if running:
                # We need to do this so that if the client closes the socket we are notified.
                webSocket.pingFreqLimited()

                percentage = getPercentage(iteration, total)
                dataId = None
                if data is not None:
                    dataId = data.id
                #logger.info('iteration %.2f of %.2f (%.1f%%) - it: %s, userId: %s' % (iteration, total, percentage,iteratorId,dataId))

                user = None
                tweet = None
                if data is None:
                    pass
                elif isinstance(data, User):
                    user = data
                elif isinstance(data, Tweet):
                    tweet = data
                    if tweet.has_user:
                        user = tweet.user
                else:
                    logger.error('Invalid data from cache, type: %s' % type(data))
                    return running

                signaler.signalEvent({SignalActions.SOCKET: updateSocket, 'percentage' : percentage, 'user_data' : user, 'tweet_data' : tweet, 'isFinished' : isFinished})
                gevent.sleep(0)
            else:
                logger.debug('Ending cache download prematurely')

            return running

        logger.debug('Starting to read data from cache...')

        # This makes sure the search is finite.
        epochNow = getEpochMs()
        if endEpoch is None or endEpoch > epochNow:
            endEpoch = epochNow

        if followerInfo or followerInfoShort:
            readUsersFromCache(twitterSession,
                               instanceId,
                               placeId = placeCacheId,
                               epochMsStartRange=startEpoch,
                               epochMsEndRange=endEpoch,
                               isFollowersLoadedRequirement=isFollowersLoadedRequirement,
                               associatedWithTweetRequirement=associatedWithTweetRequirement,
                               onIterationFunc=onCacheIteration,
                               recursive=recursiveCacheFlag,
                               userProjection=userProjection)
        else:
            readTweetsFromCache(twitterSession,
                                instanceId,
                                placeId = placeCacheId,
                                epochMsStartRange=startEpoch,
                                epochMsEndRange=endEpoch,
                                onIterationFunc=onCacheIteration,
                                retrieveUserData=True,
                                userProjection=userProjection)

        # We want to cleanup everything now since we are done.
        return False
