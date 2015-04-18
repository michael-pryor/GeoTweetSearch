<!DOCTYPE html>
<html>
    <head>
        %if defined('place_country') and defined('place_continent'):
        <title>{{project_name}} - {{instance_description}} - {{place}} / {{place_country}} / {{place_continent}}</title>
        %else:
        %if defined('place_country') and not defined('place_continent'):
        <title>{{project_name}} - {{instance_description}} - {{place}} / {{place_country}}</title>
        %else:
        %if (not defined('place_country')) and defined('place_continent'):
        <title>{{project_name}} - {{instance_description}} - {{place}} / {{place_continent}}</title>
        %else:
        <title>{{project_name}} - {{instance_description}} - {{place}}</title>
        %end
        %end
        %end


        %include includes/global.tpl static_root = static_root, problem_route = problem_route
        %include includes/map-cluster.tpl static_root = static_root
        <script src="{{static_root}}/dynamic-loading/dynamic-page-loader.js"></script>
        <script src="{{static_root}}/dynamic-loading/query-cache.js"></script>
        <script src="{{static_root}}/web-socket/socket.js"></script>
        <script src="{{static_root}}/web-socket/control-document.js"></script>
        <script src="{{static_root}}/web-socket/control-div.js"></script>
        <script src="{{static_root}}/map-followers.js"></script>
        <script src="{{static_root}}/map-drawable.js"></script>
        <script src="{{static_root}}/bulk-download.js"></script>
        <script src="{{static_root}}/performance-statistics.js"></script>
        <link rel="stylesheet" href="{{static_root}}/css/performance-statistics.css"/>
        <link rel="stylesheet" href="{{static_root}}/css/map-followers.css"/>

        <style type='text/css'>
            .historical-tweets {
                overflow: auto;
            }

            .live-tweets div.row-fluid,
            .live-tweets-header div.row-fluid,
            .historical-tweets div.row-fluid,
            .historical-tweets-header div.row-fluid,
            .influence-text-list div.row-fluid,
            .influence-text-list-header > div {
                border-bottom: 1px solid #e5e5e5;
                margin-bottom: 10px;
                margin-top: 10px;
            }

            #cache-time-slider .ui-slider-range { background: #729FCF; }
            #cache-time-slider .ui-slider-handle { border-color: #729FCF; }

            #cache-time-slider-description-max { text-align:  right; }

            body {
                min-height: 1100px;
                padding-bottom: 20px;
            }

            .main-container {
                min-height: 1050px;
                height: 90%;
            }

            .heading-div {
                height: 100px;
                margin-bottom: 21px;
                padding-bottom: 20px;
            }

        </style>
    </head>

    <body>
        <div class='container main-container'>
            %if defined('place_country_link') and defined('place_continent_link'):
            %include view-parts/title title=project_name,  buttons = [['Search Stream',instance_link,False],[place_continent, place_continent_link, False],[place_country, place_country_link, False],[place,'#',True]], website_root = website_root
            %else:
            %if defined('place_country_link') and not defined('place_continent_link'):
            %include view-parts/title title=project_name,  buttons = [['Search Stream',instance_link,False],[place_country, place_country_link, False],[place,'#',True]], website_root = website_root
            %else:
            %if (not defined('place_country_link')) and defined('place_continent_link'):
            %include view-parts/title title=project_name,  buttons = [['Search Stream',instance_link,False],[place_continent, place_continent_link, False],[place,'#',True]], website_root = website_root
            %else:
            %include view-parts/title title=project_name,  buttons = [['Search Stream',instance_link,False],[place,'#',True]], website_root = website_root
            %end
            %end
            %end
            %include view-parts/performance-statistics.tpl

            <div class='row-fluid'>
                <div class='span12'>
                    <div class='row-fluid'>
                        <div class='span12'>
                            <div id='map-heading' class='heading-div'></div>
                        </div>
                    </div>
                    <div class='row-fluid'>
                        <div class='span12'>
                            <ul class="nav nav-tabs" id="tabs-main">
                                <li class="active"><a href="#live-main-tab">Live</a></li>
                                <li><a href="#cache-main-tab">Historical</a></li>
                            </ul>
                            <div class="tab-content" id="tabs-content-main">
                                <div class="tab-pane active" id="live-main-tab">
                                    <div class="span12">
                                        <div class="row-fluid">
                                            <div class="span12">
                                                <div class="row-fluid">
                                                    <div id="TweetsByLocationWsg_header" class="scroll-padding live-tweets-header"></div>
                                                    <div id="TweetsByLocationWsg_contents" class="live-tweets scrollable"></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <div class="tab-pane" id="cache-main-tab">
                                    <div class="row-fluid" id="cache-time-slider-container">
                                        <div class="span12">
                                            <div class='row-fluid'>
                                                <div class="span8 sub-container">
                                                    <div class="row-fluid slider-description">
                                                        <div id="cache-time-slider-description-min" class="span6 pull-left"></div>
                                                        <div id="cache-time-slider-description-max" class="span6 pull-right"></div>
                                                    </div>
                                                    <div class="row-fluid" style="height: 15px;">
                                                        <div id="cache-time-slider"></div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="row-fluid">
                                        <div class="span12">
                                            <ul class="nav nav-tabs">
                                                <li class="active"><a href="#tweets" data-toggle="tab">Tweets</a></li>
                                                <li class="disabled" id="influence-tab-button"><a href="#influence" data-toggle="tab">Influence</a></li>
                                                <li><a href="#download" data-toggle="tab">Download Data</a></li>
                                            </ul>
                                            <div class="tab-content">
                                                <div class="tab-content">
                                                    <div class="tab-pane" id="download">
                                                        <div class="span12">
                                                            %include view-parts/bulk-download.tpl
                                                        </div>
                                                    </div>
                                                    <div class="tab-pane active" id="tweets">
                                                        <div class="span12">
                                                            <div class="row-fluid">
                                                                <div class="span12 scroll-padding historical-tweets-header">
                                                                    <div class="row-fluid">
                                                                        <div class='span2'>
                                                                            <b>Created</b>
                                                                        </div>
                                                                        <div class='span1'>
                                                                            <b>User</b>
                                                                        </div>
                                                                        <div class='span2'>
                                                                            <b>Location</b>
                                                                        </div>
                                                                        <div class='span7'>
                                                                            <b>Status</b>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                            <div class="row-fluid">
                                                                <div class="span12 historical-tweets scrollable" id="cache-contents"></div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div class="tab-pane" id="influence">
                                                        <div class="span12">
                                                            <div class="row-fluid">
                                                                <div class="span12">
                                                                    <div class="row-fluid">
                                                                        <ul class="nav nav-tabs" id="tabs-influence">
                                                                            <li class="active"><a href="#" id="city-influence-tab-button">Influence on cities</a></li>
                                                                            <li><a href="#" id="country-influence-tab-button">Influence on countries</a></li>
                                                                            <li><a href="#" id="continent-influence-tab-button">Influence on continents</a></li>
                                                                        </ul>
                                                                        <div class="tab-content">
                                                                            <ul class="nav nav-tabs" id="tabs-influence-type">
                                                                                <li class="active"><a href="#influence-type-tab-text">Influence Text</a></li>
                                                                                <li><a href="#influence-type-tab-map">Influence Map</a></li>
                                                                            </ul>
                                                                            <div class="tab-content">
                                                                                <div class="tab-pane active" id="influence-type-tab-text">
                                                                                    <div class="row-fluid">
                                                                                        <div class="span12">
                                                                                            <div id="influence-type-text-header" class="influence-text-list-header scroll-padding"></div>
                                                                                        </div>
                                                                                    </div>
                                                                                    <div class="row-fluid">
                                                                                        <div class="span12">
                                                                                            <div id="influence-type-text" class="influence-text-list scrollable"></div>
                                                                                        </div>
                                                                                    </div>
                                                                                </div>
                                                                                <div class="tab-pane" id="influence-type-tab-map">
                                                                                    <div class="span12">
                                                                                        <div id="influence-type-map" class="influence-map"></div>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                         </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    %include view-parts/footer.tpl
                </div>
            </div>
        </div>

        <script>
            var textHeading = $('.heading-div');
            var mapHeading = $('#map-heading');

            var pageCacheQuery;

            var influenceTextRow = $('<div class="row-fluid"><div class="span8 place-name"></div><div class="span2 place-count"></div><div class="span2 place-percentage"></div></div>');

            var influenceMap = null;
            var influenceText = null;

            var panInfluenceMapTo = function(boundingBox,switchTab,influenceType) {
                var topBound =    [boundingBox[0], boundingBox[2]];
                var bottomBound = [boundingBox[1], boundingBox[3]];

                if(switchTab) {
                    $('#tabs-influence-type a[href="#influence-type-tab-map"]').tab('show');
                }

                // fixes bug where first usage fails to zoom properly
                setTimeout(function() {
                    var bounds = [topBound,bottomBound];
                    influenceMap.leaflet_map.fitBounds(bounds);
                },100);
            };

            var getInfluenceTextRow = function(placeName, placeCount, placePercentage) {
                var influenceTextHtml = influenceTextRow.clone();
                influenceTextHtml.find('.place-name').html(placeName);
                influenceTextHtml.find('.place-count').html(placeCount);
                influenceTextHtml.find('.place-percentage').html(placePercentage);
                return influenceTextHtml;
            };

            var influenceMaps = null;

            $( document ).ready(function() {
                setServerEpochMs({{server_current_epoch}});

                var instance = '{{instance}}';
                var placeId = {{location}};
                var providerId = {{provider}};

                var performanceInstanceUrl = "{{ws_link_realtime_performance}}";
                performanceInstanceUrl = performanceInstanceUrl.replace("%s",instance);
                performanceInstanceUrl = performanceInstanceUrl + "?provider_id="+providerId+'&place_id='+placeId
                var wsRealtimePerformance = new Socket(performanceInstanceUrl, {{!socket_ops}});
                wsRealtimePerformance.add(new DocumentControl('document'));

                var mainContainerDiv = $('.main-container');
                var cacheTimeSliderContainer = $('#cache-time-slider-container');
                var onResizeFunc = function() {
                    var sizeOffset = 281 + mapHeading.height();
                    var sizeOffsetSlider = sizeOffset + 125 + 7;
                    var sizeOffsetSliderExtra = sizeOffsetSlider + 180;

                    $('.influence-map').height(mainContainerDiv.height() - sizeOffsetSliderExtra + 50);
                    $('.influence-text-list').height(mainContainerDiv.height() - sizeOffsetSliderExtra);
                    $('.live-tweets').height(mainContainerDiv.height() - sizeOffset);
                    $('#tabs-content-main').height(mainContainerDiv.height() - sizeOffset + 80);

                    var theHeight = mainContainerDiv.height() - sizeOffsetSlider - 25;
                    $('.historical-tweets').height(theHeight);
                };
                $(window).resize(onResizeFunc);
                onResizeFunc();

                setupTabs($('#tabs-main a'));
                setupTabs($('#tabs-influence a'));
                setupTabs($('#tabs-influence-type a'));

                influenceMap = new Map($("#influence-type-map"),        '{{cloud_key}}',true, mapFollowersIconCreateFunction, true);
                influenceText = $('#influence-type-text');
                influenceText = applyScrollbar(influenceText);
                influenceTabButton = $('#influence-tab-button');

                var bulkDownloadFollowerInfoShortButton = $('button[name=follower_info_short]');
                var bulkDownloadFollowerInfoFullButton = $('button[name=follower_info_full]');

                disableTabButton(influenceTabButton);
                bulkDownloadFollowerInfoFullButton.attr('disabled','disabled');
                bulkDownloadFollowerInfoShortButton.attr('disabled','disabled');


                var baseInfluenceText = influenceText.clone();


                var influenceTextByType = {};

                var map = new Map(mapHeading, '{{cloud_key}}', false, null, null, false, true);
                var mapFitView = new MapFitView(map);

                var coord = [{{place_coord[0]}}, {{place_coord[1]}}];
                mapFitView.updateBounds(coord);
                %if defined('place_bounding_box'):
                mapFitView.updateBounds([{{place_bounding_box[0]}}, {{place_bounding_box[2]}}]);
                mapFitView.updateBounds([{{place_bounding_box[1]}}, {{place_bounding_box[3]}}]);
                %end
                mapFitView.bestFitView(true);

                $('.influence-text-list-header').append(getInfluenceTextRow('<b>Location</b>', '<b># of users</b>', '<b>% of users</b>'));

                var currentlyShowing = null;

                var populateInfluenceText = function(type) {
                    var influence = undefArg(influenceTextByType[type]);
                    if(influence != null) {
                        influenceText.html(influence.html());
                    }
                };

                $('#city-influence-tab-button').click(function(e) {
                    influenceMap.showLayerGroup('city');
                    influenceMap.hideLayerGroup('continent');
                    influenceMap.hideLayerGroup('country');
                    currentlyShowing = 'city';
                    populateInfluenceText(currentlyShowing);
                }).click();

                $('#country-influence-tab-button').click(function(e) {
                    influenceMap.hideLayerGroup('city');
                    influenceMap.hideLayerGroup('continent');
                    influenceMap.showLayerGroup('country');
                    currentlyShowing = 'country';
                    populateInfluenceText(currentlyShowing);
                });

                $('#continent-influence-tab-button').click(function(e) {
                    influenceMap.hideLayerGroup('city');
                    influenceMap.showLayerGroup('continent');
                    influenceMap.hideLayerGroup('country');
                    currentlyShowing = 'continent';
                    populateInfluenceText(currentlyShowing);
                });

                // Correct issue of map in tab not displaying properly.
                updateOnTabSwitch('#tabs-influence-type a[href="#influence-type-tab-map"]', influenceMap.leaflet_map);


                // Setup live feed of tweets.
                var onNewCellCallback = function(cell, isNew) {
                    applyTooltip($(cell).find('[title]'));
                };

                applyScrollbar($('#TweetsByLocationWsg_contents'));
                var tweetTable = new DivTable("TweetsByLocationWsg",{{max_tweets}}, null, null, onNewCellCallback,'.mCSB_container');
                var wsTweet = new Socket("{{ws_link_TweetsByLocationWsg}}", {{!socket_ops}});
                wsTweet.add(new DivControl(tweetTable));

                // Setup time period selector.
                var slider = $( "#cache-time-slider" );

                var epochMaxMs = 0;
                var epochMinMs = {{startEpoch}};

                var setEpochMax = function() {
                    epochMaxMs = getEpochMs()-1000
                };
                setEpochMax();

                var updateDescription = function(uiMin, uiMax) {
                    var minDate = getNiceDateStringFromEpoch(uiMin);
                    var maxDate = getNiceDateStringFromEpoch(uiMax);
                    $("#cache-time-slider-description-min").html( "<p><b>" + minDate + "</b></p>");
                    $("#cache-time-slider-description-max").html( "<p><b>" + maxDate + "</b></p>");
                    setBulkDownloadEpochMs(uiMin, uiMax);
                };

                var sliderChanged = false;
                var updateInterval = 3000;

                var startEpoch = epochMinMs;
                var endEpoch = epochMaxMs;


                var pageCacheQueryProcessDataFunc = function(func) {
                    return function onDataFunc(data, pageElement) {
                        func(data, pageElement);
                        pageElement.find('img:last-child').tooltip({placement : 'left'});
                    }
                };

                var cacheContentsDiv = $('#cache-contents');
                pageCacheQuery = new PagedCacheQuery( cacheContentsDiv,
                                                       pageCacheQueryProcessDataFunc(buildHtml(
                                                          [ [makeDiv('span2'), makeRow(null,null,true,false)],
                                                            [makeDiv('span1')],
                                                            [makeDiv('span2')],
                                                            [makeDiv('span6') , makeRow(null,null,false,true)] ])),
                                                      'tweet',
                                                      instance,
                                                      startEpoch,
                                                      endEpoch,
                                                      placeId,
                                                      providerId,
                                                      null,
                                                      null);

                var updateInfluenceMap = function(startEpoch, endEpoch){
                    var onAlwaysFirst = function(data) {
                        data = undefArg(data);
                        if(data != null) {
                            data = data['json'];
                        }

                        if(data == null) {
                            console.warn('Failed to load influence map data, no data received');
                            return;
                        }

                        if(data.length == 0) {
                            console.info('No data in this time period');
                            return;
                        }

                        var cityData =              data['city'];
                        var countryData =           data['country'];
                        var continentData =         data['continent'];

                        var cityGeocodeList =       cityData['geocode_list'];
                        var countryGeocodeList =    countryData['geocode_list'];
                        var continentGeocodeList =  continentData['geocode_list'];

                        var cityTotal =             cityData['total'];
                        var countryTotal =          countryData['total'];
                        var continentTotal =        continentData['total'];

                        var processInfluenceDataFunc = function(type) {


                            var total = null;
                            var layerName = type;
                            influenceTextByType[type] = baseInfluenceText.clone();

                            if(type == 'city') {
                                total = cityTotal;
                            } else if(type == 'country') {
                                total = countryTotal;
                            } else if(type == 'continent') {
                                total = continentTotal;
                            } else {
                                alert('Invalid influence type: ' + type);
                            }

                            return function() {
                                    enableTabButton(influenceTabButton);
                                    bulkDownloadFollowerInfoFullButton.removeAttr('disabled');
                                    bulkDownloadFollowerInfoShortButton.removeAttr('disabled');

                                    var data = $(this);
                                    var placeId = data[0];
                                    var providerId = data[1];
                                    var placeName = data[2];
                                    var coord = data[3];
                                    var count = data[4];
                                    var percentage = (count / total) * 100;
                                    var marker = L.marker(coord);
                                    var boundingBox = data[5];
                                    marker.properties = {percentage : percentage};

                                    percentage = percentage.toFixed(2);

                                    var popup = '<b>' + placeName + '</b><br>' +
                                            'Number of followers: ' + count + '<br>' +
                                        //'Total: ' + total + '<br>' +
                                            'Percentage: ' + percentage + '%';

                                    marker.bindPopup(popup);
                                    influenceMap.addToLayerGroup(layerName,marker);

                                    var thisInfluenceTextRow = influenceTextRow.clone();

                                    thisInfluenceTextRow.find('.place-name').html('<a onclick="panInfluenceMapTo(['+ boundingBox + '],true); return false;" href="#">'+placeName+'</a>');
                                    thisInfluenceTextRow.find('.place-count').html(count);
                                    thisInfluenceTextRow.find('.place-percentage').html(percentage);

                                    var influenceList = influenceTextByType[type];
                                    influenceList.append(thisInfluenceTextRow);
                                    influenceTextByType[type] = influenceList;

                                    var isCurrentlyShowing = (currentlyShowing == type);
                                    if(isCurrentlyShowing) {
                                        // Must clone otherwise empty call will remove from influenceList too.
                                        influenceText.append(thisInfluenceTextRow.clone());
                                    }

                                    onResizeFunc();
                            };
                        };

                        influenceText.empty();
                        influenceMap.clearMap();

                        $(cityGeocodeList).each(processInfluenceDataFunc('city'));
                        $(countryGeocodeList).each(processInfluenceDataFunc('country'));
                        $(continentGeocodeList).each(processInfluenceDataFunc('continent'));
                    };
                    var onSuccess = function(data) {
                        onAlwaysFirst(data);
                    };
                    var onFail = function(data) {
                        onAlwaysFirst(data);
                    };

                    queryInfluenceCache(instance, startEpoch, endEpoch, placeId, providerId, onSuccess, onFail);
                };

                // Called when the contents of the tweet div is updated.
                var onUpdateFunc = function(startEpoch, endEpoch) {
                    updateInfluenceMap(startEpoch, endEpoch);
                };
                updateInfluenceMap(epochMinMs, epochMaxMs);

                var pagedScroller = new PagedScroller(pageCacheQuery, cacheContentsDiv, 100, updateInterval, onUpdateFunc);
                pageCacheQuery.setPageElement(pagedScroller.scrollableDiv);

                // Update slider description in real time
                // and queue contents update.
                slider.slider({
                    range: true,
                    min: epochMinMs,
                    max: epochMaxMs,
                    values: [ epochMinMs, epochMaxMs ],
                    slide: function( event, ui ) {
                        startEpoch = ui.values[0];
                        endEpoch = ui.values[1];

                        if(updateDescription != null) {
                            updateDescription(startEpoch, endEpoch);
                        }
                        pagedScroller.setEpochRange(startEpoch, endEpoch);
                    }
                });

                // Every 30 seconds extend bar so that we can scroll to the current time.
                setInterval(function() {
                    setEpochMax();
                    slider.slider("option", "max", epochMaxMs);
                }, 30000);

                updateDescription(slider.slider( "values", 0 ), slider.slider( "values", 1 ));

                pageCacheQuery.loadNextPage();

                var wsDownloadUrl = '{{ws_link_BulkDownloadDataWsg}}';
                wsDownloadUrl = wsDownloadUrl.replace('%s','{{instance}}');
                setupBulkDownload({{!socket_ops}}, wsDownloadUrl, providerId, placeId);
            });
        </script>
    </body>
</html>