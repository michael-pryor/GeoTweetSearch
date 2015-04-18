<!DOCTYPE html>
<head>
    <title>{{project_name}} - {{instance_description}}</title>

    %include includes/global.tpl static_root = static_root, problem_route = problem_route
    %include includes/map-cluster.tpl static_root = static_root
    <script src="{{static_root}}/web-socket/socket.js"></script>
    <script src="{{static_root}}/web-socket/control-document.js"></script>
    <script src="{{static_root}}/web-socket/control-map.js"></script>
    <script src="{{static_root}}/web-socket/control-div.js"></script>
    <script src="{{static_root}}/dynamic-loading/dynamic-page-loader.js"></script>
    <script src="{{static_root}}/dynamic-loading/query-cache.js"></script>
    <script src="{{static_root}}/map-followers.js"></script>
    <link rel="stylesheet" href="{{static_root}}/css/map-followers.css"/>

    <style type="text/css">

            /* Header on a vertical table,
               e.g. Name: jim <- 2 cells, name: would be the header. */
        .vertical-header {

        }

            /* Header on a vertical table,
               e.g. Name: jim <- 2 cells, jim: would be the content. */
        .vertical-content {

        }

        .vertical-row {
            border-bottom: 1px solid #e5e5e5;
            padding-bottom: 7px;
            padding-top: 7px;
            min-height:20px;
            margin-bottom:7px;
        }

            /* Entire followers list, encapsulating all rows and elements */
        .followers-div-list {
            height:250px;
        }

        /* 100% does not work for some reason!
           So, I am just hard coding which is about right

           It should be followers-div-geocode-text-contents + followers-div-geocode-text-header height */
        .followers-div-geocode-map {
            height:410px;
        }

        .followers-div-geocode-text-contents {
            height:350px;
        }

        .followers-div-geocode-text-contents-row {
            border-bottom: 1px solid #e5e5e5;
            margin-bottom: 10px;
            margin-top: 10px;
        }

        .footer {
            margin-top: 15px;
        }

        .get-followers-button {
            margin-bottom: 10px;
        }
    </style>
</head>

<body>
    <div class="container main-container">
        %include view-parts/title title=project_name,  buttons = [['Search Stream',instance_link,False],['User','#',True]], website_root = website_root

        <div class="row-fluid">
            <div class="span12">
                <div class="row-fluid">
                    <div class="span12">
                        <div id="UserWsg_div_contents"></div>
                    </div>
                </div>
                %include view-parts/footer.tpl
            </div>
        </div>
    </div>

    <script>
        var setPageTitle = function(title) {
            $('#titleDiv').html(title);
            document.title = '{{project_name}} - {{instance_description}} - ' + title;
        };

        var pageCacheQuery = null;
        var currentlySelected = null;

        var cookiePicturesEnabled = 'user-follower-pictures-enabled';
        var isPicturesEnabled = null;

        var wsUser = null;
        var userFollowersMap = null;

        var onFollowersUpdated = function(isImage) {
            return function(pageElement) {
                if(isImage) {
                    applyTooltip(pageElement.find('.twitter-profile-image'),null,null,'left', 'body');
                } else {
                    var imageUrl = function() {
                        return '<img class="twitter-profile-image" src="' + $(this).attr('image_url') + '"></img>';
                    };
                    applyTooltip(pageElement.find('.twitter-username'), imageUrl, true, 'left', 'body');
                }
            };
        };

        var processFuncImage = processCacheDataFuncUser(12, makeImageFromUserDataProcess('twitter-profile-image'), 'span1 follower-square-image', onFollowersUpdated(true));
        var processFuncText = processCacheDataFuncUser(4, makeTextFromUserData('twitter-username'), 'span3 follower-square-text', onFollowersUpdated(false));

        $( document ).ready(function() {
            isPicturesEnabled = undefArg($.cookie(cookiePicturesEnabled));
            console.info('Retrieved cookie pictures enabled flag ' + isPicturesEnabled);

            if(isPicturesEnabled == null || (isPicturesEnabled != 0 && isPicturesEnabled != 1)) {
                isPicturesEnabled = true;
                updatePicturesEnabledCookie();
            } else {
                isPicturesEnabled = parseInt(isPicturesEnabled) != 0;
            }

            if(isPicturesEnabled) {
                currentlySelected = processFuncImage;
            } else {
                currentlySelected = processFuncText;
            }

            var userDiv = new DivTable("UserWsg_div");

            wsUser = new Socket("{{ws_link_UserWsg}}", {{!socket_ops}});
            wsUser.add(new DivControl(userDiv));
        });

        var setupFollowerLocationMap = function() {
            userFollowersMap = new Map($("#UserWsg_follower_map"),'{{cloud_key}}',true, mapFollowersIconCreateFunction, true);
            wsUser.removeByName("UserWsg_follower_map");
            wsUser.add(new MapControl(userFollowersMap));
        };

        var panMapTo = function(coord) {
            if(userFollowersMap == null) {
                return;
            }
            var leafletMap = userFollowersMap.leaflet_map;
            leafletMap.setView(coord, 9);
        };

        var updatePicturesEnabledCookie = function() {
            var value = 0;
            if(isPicturesEnabled) {
                value = 1;
            }

            $.cookie(cookiePicturesEnabled, value, {expires : 7});
            console.info('Set cookie pictures enabled flag to ' + isPicturesEnabled);
        };

        var onFollowerListDisplayButton = function(id) {
            if(pageCacheQuery == null) {
                return;
            }

            if(id == 2 && currentlySelected === processFuncImage) {
                currentlySelected = processFuncText;
            } else if(id == 1) {
                currentlySelected = processFuncImage;
            } else {
                // We are already in the correct state.
                return;
            }

            isPicturesEnabled = currentlySelected === processFuncImage;

            updatePicturesEnabledCookie();

            pageCacheQuery.setProcessDataFunc(currentlySelected);
        };

        var setupFollowersList = function() {
            var masterElement = $('#followers-list');
            masterElement.append('<div class="row-fluid">' +
                                    '<div class="span12">' +
                                        '<div class="btn-group" data-toggle="buttons-radio">' +
                                            '<button type="button" class="btn btn-small" id="enable-profile-pictures-button" onclick="onFollowerListDisplayButton(1); return false;">Profile Pictures</button>' +
                                            '<button type="button" class="btn btn-small" id="enable-user-names-button" onclick="onFollowerListDisplayButton(2); return false;">User Names</button>' +
                                        '</div>' +
                                    '</div>' +
                                 '</div><br>');

            if(isPicturesEnabled) {
                masterElement.find('#enable-profile-pictures-button').button('toggle');
            } else {
                masterElement.find('#enable-user-names-button').button('toggle');
            }

            var row = $('<div class="row-fluid"></div>');
            var theElement = $('<div class="span12 followers-div-list scrollable"></div>');
            row.append(theElement);

            masterElement.append(row);

            console.info('Setting up followers list with picture enabled flag: ' + isPicturesEnabled);

            pageCacheQuery = new PagedCacheQuery(theElement, currentlySelected, 'user', '{{instance}}', null, null, null, null, {{user_id}}, 'name-only');
            var pagedScroller = new PagedScroller(pageCacheQuery, theElement, 100, null);
            pageCacheQuery.setPageElement(pagedScroller.scrollableDiv);
            pageCacheQuery.loadNextPage();
        }

        var applyScrollbars = function() {
            applyScrollbar($('.followers-div-geocode-text-contents'));
        };
    </script>
</body>