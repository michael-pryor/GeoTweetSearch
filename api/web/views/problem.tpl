<!DOCTYPE html>
<html>
    <head>
        <title>{{project_name}} - Serious problem..</title>

        %include includes/global.tpl static_root = static_root

        <style type="text/css">
            .main-container {
                height:  90%;
                min-height: 500px;
            }

            .problem-image {
                display: block;
                margin-left: auto;
                margin-right: auto }
        </style>
    </head>

    <body>
        <div class="container main-container">
            %include view-parts/title title=project_name,  buttons = [['Search Stream','#',True]], website_root = website_root
            <div class='row-fluid'>
                <div class='span12'>
                    <p>Something went horribly wrong...</p>
                    <br>
                    <p><b>Problem description</b></p>
                    <p>{{ERROR}}</p>
                    <br>
                    <img class='problem-image' src='{{static_root}}/problem.png'>
                </div>
        </div>
    </body>
</html>