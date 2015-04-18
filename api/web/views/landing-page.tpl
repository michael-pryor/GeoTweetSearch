<!DOCTYPE html>
<html>
    <head>
        <title>{{project_name}}</title>

        %include includes/global.tpl static_root = static_root, problem_route = problem_route
        %include includes/map.tpl static_root = static_root
        <script src="{{static_root}}/map-drawable.js"></script>
        <script src="{{static_root}}/map-instance.js"></script>

        <style type="text/css">
            .pagination {
                text-align: center;
            }

            .thumbnail {
                max-width: 600px;
                height: 450px;
                margin:0 auto;
                margin-bottom: 10px;
            }

            .thumbnail-text {
                height: 45px;
            }

            .highlight {
                border-color: red;
            }

            body {
                height: auto;
                margin-bottom: 20px;
            }

            .pagination {
                padding-bottom: 15px;
            }
        </style>
    </head>

    <body>
        <div class="container main-container">
            %include view-parts/title title=project_name, buttons=[], website_root = website_root

            <div class="row-fluid">
                <div class="span12">
                    <div class="row-fluid">
                        <div class="span12">
                            <h4>Welcome</h4>
                            <p>Welcome to GeoTweetSearch! This website is a powerful tool for analysing Twitter streams. To get started <a href="{{website_root}}/oauth/sign_in">create a search stream</a> or view one below.</p>
                            <p>You can read a comprehensive report on this project <a href="{{static_root}}/report.pdf">here</a>.</p>
                            <br>
                        </div>
                    </div>

                    <div class="row-fluid">
                        <div class="span12">
                            <ul class="thumbnails" id="instance-thumbnails">
                                %for row in instances:
                                    <div class='row-fluid'>
                                        %for item in row:
                                            <li class="span{{thumbnail_span}}">
                                                <div class="thumbnail  thumbnail-item">
                                                    <div class="caption">
                                                        <h3>Search Stream</h3>
                                                        <div class='instance-map' style='width:100%; height:300px;'><div class='instance-map-data' hidden>{{!item[2]}}</div></div>
                                                        <p class='thumbnail-text'>{{item[1]}}</p>
                                                        <p><a href="{{item[0]}}" class="btn btn-primary">View</a></p>
                                                    </div>
                                                </div>
                                            </li>
                                        %end
                                    </div>
                                %end
                                <div class='row-fluid'>
                                    %if defined('pagination_previous') or defined('pagination_next'):
                                        <div class="pagination">
                                            <ul>
                                                %if defined('pagination_previous'):
                                                    <li><a href="{{pagination_previous}}">Prev</a></li>
                                                %else:
                                                    <li class="disabled"><a>Prev</a></li>
                                                %end

                                                %for page in pagination:
                                                    %if page[2]:
                                                        <li><a href="{{page[1]}}" class="active"><b>{{page[0]}}</b></a></li>
                                                    %else:
                                                        <li><a href="{{page[1]}}">{{page[0]}}</a></li>
                                                    %end
                                                %end

                                                %if defined('pagination_next'):
                                                    <li><a href="{{pagination_next}}">Next</a></li>
                                                %else:
                                                    <li class="disabled"><a>Next</a></li>
                                                %end
                                            </ul>
                                        </div>
                                    %end
                                </div>
                            </ul>
                        </div>
                    </div>
                    %include view-parts/footer.tpl
                </div>
            </div>
        </div>

        <script>
            $(document).ready(function() {
                var instanceThumbnailsContainer = $('#instance-thumbnails');
                var instanceThumbnailMaps = instanceThumbnailsContainer.find('.instance-map');
                $(instanceThumbnailMaps).each(function() {
                    var map = new Map($(this), '{{cloud_key}}', false, null, null, false, true);
                    var drawableMapInstance = new DrawableMapInstance(map,null,null,null,null,null,null,null,null,null,false);
                    var mapData = $(this).find('.instance-map-data').html();
                    drawableMapInstance.loadData($.parseJSON(mapData));
                    drawableMapInstance.drawableMap.bestFitView(true);
                });

                var thumbnails = $('.thumbnail-item');
                thumbnails.hover(function(e){
                    $(this).addClass('highlight');
                },function(e){
                    $(this).removeClass('highlight');
                });
            });
        </script>
    </body>
</html>