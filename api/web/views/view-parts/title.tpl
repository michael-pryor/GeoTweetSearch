<div class="navbar" id="title-nav-bar">
    <div class="navbar-inner" id="title-nav-bar-inner">
        <a class="brand" href="{{website_root}}">{{title}}</a>
        <ul class="nav">
            %if defined('buttons'):
                %for item in buttons:
                    %if item[2]:
                        <li class="active"><a href="{{!item[1]}}">{{item[0]}}</a></li>
                    %else:
                        <li><a href="{{!item[1]}}">{{item[0]}}</a></li>
                    %end
                %end
            %end
        </ul>
        <ul class="nav pull-right">
            %if defined('buttons_right'):
                %for item in buttons_right:
                    %if item[2]:
                        <li class="active"><a href="{{!item[1]}}">{{item[0]}}</a></li>
                    %else:
                        <li><a href="{{!item[1]}}">{{item[0]}}</a></li>
                    %end
                %end
            %end
            %if (not defined('prevent_build_button')) or not prevent_build_button:
                <li><a href="{{website_root}}/oauth/sign_in" target='_blank'>Build Search Stream</a></li>
            %end
        </ul>
    </div>
</div>