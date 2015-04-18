<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/html">
    <head>
        <title>{{project_name}} - Build Search Stream</title>

        %include includes/global.tpl static_root = static_root, problem_route = problem_route
        %include includes/map.tpl static_root = static_root
        <script src="{{static_root}}/map-drawable.js"></script>
        <script src="{{static_root}}/map-instance.js"></script>
        <script src="{{static_root}}/instance-help.js"></script>
        <script src="{{static_root}}/dynamic-loading/dynamic-page-loader.js"></script>
        <script src="{{static_root}}/dynamic-loading/query-geocode.js"></script>

        <style type="text/css">
            .main-container {
                min-height: 700px;
                height: 90%;
            }
        </style>
    </head>

    <body>
        %if defined('error'):
        <div class="alert alert-error" id="error-div">
            <button type="button" class="close" data-dismiss="alert">&times;</button>
            {{error}}
        </div>
        %end

        <div class="container main-container">
            %include view-parts/title title=project_name,  buttons = [['Build Search Stream','#',True]], prevent_build_button=True, website_root = website_root
            <div class="row-fluid">
                <div id="contents" class="span12">
                    <div class="row-fluid">
                        <form method="POST" action="{{post_address}}" id="theForm">


                            <div class="row-fluid">
                                <div class="span8">
                                    <div class='row-fluid'>
                                        <div class='span12'>
                                            <input id="input-keywords" type="text" name="keywords" class="span12" value="{{keywords}}" placeholder="Keywords e.g. apple,orange,car">
                                        </div>
                                    </div>
                                    <div class='row-fluid'>
                                        <div class='span12'>
                                            <div class="row-fluid">
                                                <div class="span12">
                                                    <br>
                                                    <div class="btn-toolbar">
                                                        <div class="btn-group" data-toggle="buttons-checkbox">
                                                            <button type="button" class="btn btn-success trigger-geographical-help" id="button-geographical-filter">Geographical Filter</button>
                                                            <button type="button" class="btn btn-danger trigger-influence-help" id="button-influence-source">Influence Source</button>
                                                        </div>
                                                        <div class="btn-group">
                                                            <button type="button" class="btn btn-info trigger-geographical-help" id="begin-draw-button">Select Area</button>
                                                            <button type="button" class="btn btn-info trigger-geographical-help" id="delete-last-draw-button" disabled>Undo</button>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>

                                            <div class="row-fluid">
                                                <div class="span12">
                                                    <input id="input-geocode-search" type="text" class="span12 trigger-geographical-help" placeholder="Search for city, country or continent e.g. England" autocomplete="off">
                                                </div>
                                            </div>

                                            <div class="row-fluid">
                                                <div class="span12">
                                                    <div id="map-select-area" class="span12 border padding"></div>
                                                </div>
                                            </div>

                                            <div class="row-fluid">
                                                <div class="span12">
                                                    <br>
                                                    <input id="input-instance-setup-code" name="instance_setup_code" type="text" class="span12" value="{{instance_setup_code}}" placeholder="Setup code (ignore unless provided with one)">
                                                </div>
                                            </div>

                                            <div class="row-fluid">
                                                <div class="span12">
                                                    <br>
                                                    <button type="submit" class="btn btn-primary" id="create-instance-button">Create</button>
                                                </div>
                                            </div>

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

                            <input type="hidden" name="oauth_token" value="{{oauth_token}}"/>
                            <input type="hidden" name="oauth_secret" value="{{oauth_secret}}"/>
                            <input type="hidden" id="regions" name="regions" value="{{regions}}"/>
                        </form>
                    </div>
                </div>
            </div>
            %include view-parts/footer.tpl
        </div>

        <script>
            $.cookie.json = true;
            var accordion = $('#accordionHelp');
            var accordionHelpKeywords = new CollapsibleEx(false, accordion, $('#collapseInstanceHelpOne'));
            var accordionHelpGeographical = new CollapsibleEx(false, accordion, $('#collapseInstanceHelpTwo'));
            var accordionHelpInfluence = new CollapsibleEx(false, accordion, $('#collapseInstanceHelpThree'));

            var buttonGeographicalFilter = $('#button-geographical-filter');
            var buttonInfluenceSource = $('#button-influence-source');

            var inputKeywords = $('#input-keywords');
            var inputGeocodeSearch = $('#input-geocode-search');

            var theForm = $('#theForm');

            var mapDiv = $($('#map-select-area'));

            var mainContainerDiv = $('.main-container');
            var onResizeFunc = function() {
                var mainContainerDivHeight = mainContainerDiv.height();
                mapDiv.height(mainContainerDivHeight - 375);
                $('.accordion-inner-instance-help').height(mainContainerDivHeight - 305);
            };
            $(window).resize(onResizeFunc);
            onResizeFunc();


            var buttonCreateInstance = $('#create-instance-button');
            buttonCreateInstance.click(function(e) {
                buttonCreateInstance.html('Creating...');
                buttonCreateInstance.attr('disabled','disabled');

                theForm.submit();
            });

            var instanceHelp = new InstanceHelp(accordionHelpKeywords, accordionHelpInfluence, accordionHelpGeographical);

            inputKeywords.focus(instanceHelp.showKeywordsHelp);

            inputGeocodeSearch.focus(function(e) {
                var mapMode = drawableMapInstance.getMapMode();
                if(mapMode == INFLUENCE_SOURCE) {
                    instanceHelp.showInfluenceHelp();
                } else if(mapMode == GEOGRAPHICAL_FILTER) {
                    instanceHelp.showGeographicalHelp();
                } else if(mapMode == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
                    if(instanceHelp.getHelpShowing() == HELP_KEYWORDS) {
                        instanceHelp.showGeographicalHelp();
                    }
                }
                $(this).val('');
            });

            var buttonBeginDraw = $('#begin-draw-button');
            var buttonDeleteLastDraw = $('#delete-last-draw-button');

            var map = new Map(mapDiv, '{{cloud_key}}');

            var totalAvailableGeographicalFilters = {{max_geographical_filters}};

            var onTwitterFilterChange = function(numGeographicFiltersUsed) {
                if(inputKeywords.val().length > 0 || numGeographicFiltersUsed > 0) {
                    buttonCreateInstance.removeAttr('disabled');
                } else {
                    buttonCreateInstance.attr('disabled','disabled');
                }
            };

            var onGeographicalFilterButtonActive = function() {
                instanceHelp.showGeographicalHelp();
            };

            var onInfluenceSourceButtonActive = function() {
                instanceHelp.showInfluenceHelp();
            };

            var drawableMapInstance = new DrawableMapInstance(map, $('#regions'), buttonBeginDraw, buttonDeleteLastDraw, buttonGeographicalFilter, buttonInfluenceSource, totalAvailableGeographicalFilters, onGeographicalFilterButtonActive, onInfluenceSourceButtonActive, onTwitterFilterChange);
            var drawableMap = drawableMapInstance.drawableMap;

            inputKeywords.on('input', function() {
                onTwitterFilterChange(drawableMapInstance.getNumGeographicFiltersUsed());
            });

            // Reload data, if we start instance and then shut it down this preserves
            // the state we set it up in.
            drawableMapInstance.loadData({{!regions}});

            var typeAheadCache = {};

            var nextTypeAheadQuery = null;
            var lastTypeAheadQuery = null;

            setInterval(function() {
                if(lastTypeAheadQuery != nextTypeAheadQuery) {
                    var thisQuery = nextTypeAheadQuery;
                    lastTypeAheadQuery = thisQuery;

                    var query = thisQuery[0];
                    var callback = thisQuery[1];
                    queryGeocodeSearch(query, callback);
                }
            },500);

            var typeAheadSource = function(query, process) {
                var onSuccess = function(data) {
                    var json = data['json'];
                    var placeNames = [];
                    $(json).each(function() {
                        var placeName = this[3];
                        typeAheadCache[placeName] = this;
                        placeNames.push(placeName);
                    });
                    process(placeNames);
                };

                nextTypeAheadQuery = [query,onSuccess];
            };

            var typeAheadUpdater = function(item) {
                if(!(item in typeAheadCache)) {
                    console.error('Could not find item to highlight in type ahead cache');
                    return null;
                }

                var data = typeAheadCache[item];
                var providerId = data[0]['providerId'];
                var placeId = data[0]['placeId'];
                var cacheId = data[0];
                var boundingBox = data[1];
                var coordinate = data[2];
                var placeName = data[3];

                typeAheadCache = {};

                var mapMode = drawableMapInstance.getMapMode();

                var topBound =    [boundingBox[0], boundingBox[2]];
                var bottomBound = [boundingBox[1], boundingBox[3]];
                var bounds = null;
                if(mapMode == GEOGRAPHICAL_FILTER || mapMode == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {


                    drawableMap.addRectangleArea(topBound,
                                                 bottomBound, {'placeName' : placeName});
                    bounds = [topBound, bottomBound];
                }

                if(mapMode == INFLUENCE_SOURCE || mapMode == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
                    drawableMap.addMarker(coordinate, {'cacheId' : cacheId, 'placeName' : placeName});

                    if(mapMode == INFLUENCE_SOURCE) {
                        bounds = [topBound, bottomBound];
                    }
                }

                if(bounds != null) {
                    map.leaflet_map.fitBounds(bounds);
                }

                return item;
            };

            inputGeocodeSearch.typeahead(  {source : typeAheadSource,
                                            updater : typeAheadUpdater,
                                            items : 100 });// there are limits on server side to keep this safe.
        </script>
    </body>
</html>