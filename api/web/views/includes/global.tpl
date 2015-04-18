<script src="{{static_root}}/third-party/jquery/jquery.js"></script>

<link rel="stylesheet" href="{{static_root}}/third-party/jquery-ui/css/ui-lightness/jquery-ui.custom.min.css" />
<script src="{{static_root}}/third-party/jquery-ui/js/jquery-ui.custom.min.js"></script>

<script src="{{static_root}}/third-party/jquery-cookie/jquery-cookie.js"></script>

<script src="{{static_root}}/third-party/jquery-mousewheel/jquery.mousewheel.min.js"></script>
<script src="{{static_root}}/third-party/jquery-custom-scrollbar/jquery.mCustomScrollbar.min.js"></script>
<link href="{{static_root}}/third-party/jquery-custom-scrollbar/jquery.mCustomScrollbar.css" rel="stylesheet" media="screen">

<link href="{{static_root}}/third-party/bootstrap/css/bootstrap.min.css" rel="stylesheet" media="screen">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="{{static_root}}/third-party/bootstrap/css/bootstrap-responsive.css" rel="stylesheet">
<script src="{{static_root}}/third-party/bootstrap/js/bootstrap.min.js"></script>

<script src="{{static_root}}/utility.js"></script>

<link rel="stylesheet" type="text/css" href="{{static_root}}/css/style-sheet.css">

<script>
    // Support internet explorer.
    if (typeof console == "undefined") {
        this.console = {log: function() {},
                        info: function() {},
                        warn: function() {},
                        error: function() {}};
    }

    // Old or rubbish browsers don't support web sockets.
    %if defined('problem_route'):
    if(typeof WebSocket !== "function") {
        window.location = "{{problem_route}}?error=Your web browser does not support HTML5 web sockets. As a result you cannot use this website, please upgrade your browser to the latest version or use a better browser.";
    }
    %end
</script>


