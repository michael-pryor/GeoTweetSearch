<!DOCTYPE html>
<html>
    <head>
        <title>{{project_name}} - {{instance_description_with_prefix}}</title>

        %include includes/global.tpl static_root = static_root, problem_route = problem_route
        %include includes/map-cluster.tpl static_root = static_root
        <script src="{{static_root}}/web-socket/socket.js"></script>
        <script src="{{static_root}}/web-socket/control-document.js"></script>
        <script src="{{static_root}}/web-socket/control-map.js"></script>
        <script src="{{static_root}}/map-drawable.js"></script>
        <script src="{{static_root}}/map-instance.js"></script>
        <script src="{{static_root}}/instance-help.js"></script>
        <script src="{{static_root}}/bulk-download.js"></script>
        <script src="{{static_root}}/performance-statistics.js"></script>
        <link rel="stylesheet" href="{{static_root}}/css/performance-statistics.css"/>

        <style type="text/css">
            .main-container {
                height:  90%;
                min-height: 800px;
            }
            #main-tab-content {
                overflow: hidden;
            }

            #cache-time-slider .ui-slider-range { background: #729FCF; }
            #cache-time-slider .ui-slider-handle { border-color: #729FCF; }
            #cache-time-slider .ui-slider-handle, #num-bytes-per-batch-slider  .ui-slider-handle{
                width: 15px;
                height: 15px;
                margin-top: 2px;
            }

            .accordion-inner-bulk-download {
                height: 470px;
            }
        </style>
    </head>



    <body>
        <div class="container main-container">
            %include view-parts/title title=project_name,  buttons = [['Search Stream','#',True]], website_root = website_root
            %include view-parts/performance-statistics.tpl
            <div class='row-fluid'>
                <div class='span12'>
                    <div class='row-fluid'>
                        <div class='span12'>
                            <ul class="nav nav-tabs" id="tabs-main">
                                <li class="active"><a id="details-tab-button" href="#details-tab">Details</a></li>
                                <li class="hide" id="management-tab-button-li"><a id="management-tab-button" href="#management-tab">Management</a></li>
                                <li><a id="maps-tab-button" href="#map-tab">Map</a></li>
                                <li><a id="download-tab-button" href="#download-tab">Download Data</a></li>
                            </ul>
                            <div class="tab-content" id="main-tab-content">
                                <div class="tab-pane active" id="details-tab">
                                    <div class="row-fluid">
                                        <div class="span12">
                                            <div class="row-fluid">
                                                <div class="span8">
                                                    <div class='row-fluid'>
                                                        <div class='span12'>
                                                            <input id="input-keywords" type="text" name="keywords" class="span12" value="{{keywords_display}}" disabled>
                                                        </div>
                                                    </div>
                                                    <div class='row-fluid'>
                                                        <div class="span12">
                                                            <div id="map-instance-information" class="span12"></div>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div class="span4">
                                                    <div class="row-fluid">
                                                        <div class="span12">
                                                            %include view-parts/instance-help.tpl
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="tab-pane" id="map-tab">
                                    <div class="span12">
                                        <div class="row-fluid">
                                            <div class='span12'>
                                                <ul class="nav nav-tabs" id="tabs-map-places">
                                                    <li class="active"><a id="city-tab-button" href="#">City</a></li>
                                                    <li><a id="country-tab-button" href="#">Country</a></li>
                                                    <li><a id="continent-tab-button" href="#">Continent</a></li>
                                                </ul>
                                                <div class="tab-content">
                                                    <div class="tab-pane active">
                                                        <div class="span12">
                                                            <div class="row-fluid">
                                                                <div class='span12'>
                                                                    <div id="map" style="width: 100%;"></div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="tab-pane" id="management-tab">
                                    <div class="span12">
                                        <div class="row-fluid">
                                            <div class='span12'>
                                                <div id='div-terminate'>
                                                    <h4>Terminate</h4>
                                                    <p>After terminating your instance all data will be wiped and cannot be recovered. Only terminate your instance
                                                    after you have downloaded all data that you require.</p>
                                                    <form method="POST" action="{{post_address}}" id="terminateForm">
                                                        <button type="submit" class="btn btn-danger btn-large" id="terminate-instance-button">Terminate</button>
                                                        <input type="hidden" name="oauth_token" id="oauth_token" value=""/>
                                                        <input type="hidden" name="oauth_secret" id="oauth_secret" value=""/>
                                                    </form>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <div class="tab-pane" id="download-tab">
                                    <div class="row-fluid">
                                        <div class="span12">
                                            %include view-parts/bulk-download.tpl include_time_period_bar=True
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

        <script>
            $(document).ready(function () {
                setServerEpochMs({{server_current_epoch}});

                var wsRealtimePerformance = new Socket("{{ws_link_realtime_performance}}", {{!socket_ops}});
                wsRealtimePerformance.add(new DocumentControl('document'));

                var accordion = $('#accordionHelp');
                var accordionHelpKeywords = new CollapsibleEx(false, accordion, $('#collapseInstanceHelpOne'));
                var accordionHelpGeographical = new CollapsibleEx(false, accordion, $('#collapseInstanceHelpTwo'));
                var accordionHelpInfluence = new CollapsibleEx(false, accordion, $('#collapseInstanceHelpThree'));
                accordionHelpKeywords.show();
                var instanceHelp = new InstanceHelp(accordionHelpKeywords, accordionHelpInfluence, accordionHelpGeographical);

                setupTabs($('#tabs-map-places a'));
                setupTabs($('#tabs-main a'));

                var mapDiv = $('#map');
                var map =               new Map(mapDiv, '{{cloud_key}}', true);
                var controlMap =        new MapControl(map);
                var ws = new Socket("{{ws_link_LocationMapWsg}}", {{!socket_ops}});
                ws.add(controlMap);

                var mapInstanceInformationDiv = $('#map-instance-information');
                var mapInstanceInformation = new Map(mapInstanceInformationDiv, '{{cloud_key}}', false, null, null, false);

                var mainContainerDiv = $('.main-container');
                var onResizeFunc = function() {
                    mapInstanceInformationDiv.height(mainContainerDiv.height() - 210);
                    mapDiv.height(mainContainerDiv.height() - 228);
                    $('.accordion-inner-instance-help').height(mainContainerDiv.height() - 300);
                    $('#main-tab-content').height(mainContainerDiv.height() - 160);
                    //$('.accordion-inner-bulk-download').height(mainContainerDiv.height() - 250);
                };
                $(window).resize(onResizeFunc);
                onResizeFunc();

                var onGeographicalAction = function() {

                };
                var onInfluenceSourceAction = function() {

                };

                var drawableMapInstance = new DrawableMapInstance(mapInstanceInformation, null, null, null, null, null, null, onGeographicalAction, onInfluenceSourceAction, null);
                drawableMapInstance.loadData({{!instance_map_data}});
                drawableMapInstance.drawableMap.bestFitView();

                // Correct issue of map in tab not displaying properly.
                updateOnTabSwitch('#tabs-main a[href="#map-tab"]', map.leaflet_map);
                updateOnTabSwitch('#tabs-main a[href="#details-tab"]', drawableMapInstance.drawableMap.map.leaflet_map);

                var buttonTerminateInstance = $('#terminate-instance-button');
                var dataInstanceName = '{{instance_name}}';
                var divManagementTabButtonLi = $('#management-tab-button-li');

                var cookieInstancesByName = $.cookie('_instancesByName');
                if(cookieInstancesByName == null) {
                    console.warn('No instance authorisation structure found in cookies');
                } else {
                    cookieInstancesByName = decodeCookieFromBottle(cookieInstancesByName);
                    cookieInstancesByName = $.parseJSON(cookieInstancesByName);
                    var dataInstanceAuth = undefArg(cookieInstancesByName[dataInstanceName]);

                    if(dataInstanceAuth == null) {
                        console.info('Management authorisation not detected for this instance');
                    } else {
                        var dataAuthToken = undefArg(dataInstanceAuth[0]);
                        var dataAuthSecret = undefArg(dataInstanceAuth[1]);
                        if(dataAuthToken == null || dataAuthSecret == null) {
                            console.warn('Invalid management authorisation detected for this instance');
                        } else {
                            console.info('Management authorisation detected for this instance, auth token: ' + dataAuthToken + ', auth secret: ' + dataAuthSecret);
                            $('#oauth_token').val(dataAuthToken);
                            $('#oauth_secret').val(dataAuthSecret);

                            divManagementTabButtonLi.removeClass('hide');
                        }
                    }
                }

                buttonTerminateInstance.click(function() {
                    $(this).html('Terminating...');
                    $(this).attr('disabled','disabled');
                    $('#terminateForm').submit();
                });

                var cityTab = $('#city-tab-button');
                var countryTab = $('#country-tab-button');
                var continentTab = $('#continent-tab-button');

                countryTab.click(function(e) {
                    map.hideLayerGroup('city');
                    map.hideLayerGroup('continent');
                    map.showLayerGroup('country');
                });
                cityTab.click(function(e) {
                    map.hideLayerGroup('country');
                    map.hideLayerGroup('continent');
                    map.showLayerGroup('city');
                });
                continentTab.click(function(e) {
                    map.hideLayerGroup('city');
                    map.hideLayerGroup('country');
                    map.showLayerGroup('continent');
                });
                cityTab.click();

                setupBulkDownload({{!socket_ops}}, '{{ws_link_BulkDownloadDataWsg}}', null, null, {{start_epoch}}, getEpochMs());

                var setEpochMax = function() {
                    epochMaxMs = getEpochMs()-1000
                };
                setEpochMax();
                // Every 30 seconds extend bar so that we can scroll to the current time.
                setInterval(function() {
                    setEpochMax();
                    cacheTimeSlider.slider("option", "max", epochMaxMs);
                }, 30000);

            });
        </script>
    </body>
</html>