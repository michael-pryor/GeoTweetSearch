jQuery.fn.outerHTML = function() {
    return jQuery('<div />').append(this.eq(0).clone()).html();
};

function insertInArray(arr, key, value) {
    value = undefArg(value);
    key = undefArg(key);

    if(key != null && value != null) {
        arr[key] = value;
    }
}

function isFunction(val) {
    return val instanceof Function
}

function applyTooltip($elements, title, html, placement, container) {
    title = undefArg(title, null);
    html = undefArg(html, false, true);
    placement = undefArg(placement, 'left');
    container = undefArg(container, null);

    $elements.each(function() {
        var arr = {};

        insertInArray(arr, 'title', title);
        insertInArray(arr, 'html', html);
        insertInArray(arr, 'placement', placement);

        if(container != null){
            insertInArray(arr, 'container', container);
        }

        $(this).tooltip(arr);
    })
}

// Bottle encodes characters into forms like \054.
// I couldn't find a good function to reverse this but
// for my uses I only need to reverse one character.
function decodeCookieFromBottle(str) {
    return str.replace(/\\054/g,',');
}

function ObjectMap() {
    this.map = {};

    this.add = function(itemHashKey,item) {
        if(itemHashKey in this.map) {
            return false;
        }
        else {
            this.map[itemHashKey] = item;
            //console.debug("Added item with key " + itemHashKey + " to hash map");
            return true;
        }
    };

    this.remove = function(itemHashKey) {
        if(itemHashKey in this.map) {
            var item = this.map[itemHashKey];
            delete this.map[itemHashKey];
            return item;
        }
        else {
            console.warn("Failed to remove item with key: " + itemHashKey + " from hash map, does not exist");
            return null;
        }
    };

    this.contains = function(itemHashKey) {
        return itemHashKey in this.map;
    };

    this.get = function(itemHashKey) {
        if (!this.contains(itemHashKey)) {
            return null;
        }

        return this.map[itemHashKey];
    };
}


function setElementInnerHtml(element, html) {
    element.innerHTML = html;

    var x = element.getElementsByTagName("script");
    for(var i=0;i<x.length;i++)
    {
        executeJavascript(x[i].text);
    }
}

function executeJavascript(javascript) {
    eval(javascript);
}

function toggleScrollbarCustomY(object, marginWithScroll, marginWithoutScroll) {
    if(object.style.overflowY != '' && object.style.overflowY != 'scroll') {
        object.style.overflowY = 'scroll';
        object.style.marginRight = marginWithScroll;
        return false;
    } else {
        object.style.overflowY = 'hidden';
        object.style.marginRight = marginWithoutScroll;
        return true;
    }
}


function toggleScrollbarY(object) {
    return toggleScrollbarCustomY(object, '12px', '24px');
}

function toggleScrollbarByNameY(objectName) {
    var obj = document.getElementById(objectName);
    return toggleScrollbarY(obj);
}


var offsetEpochMs = 0;
function setServerEpochMs(serverEpochMs) {
    offsetEpochMs = getEpochMs() - serverEpochMs;
    console.info('Epoch offset is ' + offsetEpochMs);
}

function getEpochMs() {
    return (new Date).getTime() - offsetEpochMs;
}

function buildHtml(spec) {
    return function(data, pageElement) {
        var fullHtml = '';
        $(data).each(function (index, row) {
            for(var n = 0;n<row.length;n+=1) {
                var html = row[n];
                var specElement = spec[n];
                for(var x = 0;x<specElement.length;x++) {
                    html = specElement[x](html);
                }
                fullHtml += html;
            }

        });
        pageElement.append(fullHtml);
    }
}

// These only work properly if tabs are setup with data-toggle.
function disableTabButton(selector) {
    var aSelector = selector.find('a');

    if(!undefArg(aSelector.attr('old_href'))) {
        selector.addClass('disabled');
        var href = aSelector.attr('href');
        aSelector.removeAttr('href');
        aSelector.attr('old_href',href);
        aSelector.removeAttr('data-toggle');
    }
}

function enableTabButton(selector) {
     var aSelector = selector.find('a');

     if(undefArg(aSelector.attr('old_href'))) {
        aSelector.attr('href',aSelector.attr('old_href'));
        aSelector.removeAttr('old_href');
        selector.removeClass('disabled');
        aSelector.attr('data-toggle','tab');
    }
}

function applyScrollbar(element, onScrollReachBottom, dynamic) {
    dynamic = undefArg(dynamic, true);

    onScrollReachBottom = undefArg(onScrollReachBottom);

    var scrollFunc = function() {
        if(onScrollReachBottom != null) {
            onScrollReachBottom();
        }
    };

    element.mCustomScrollbar({   advanced : {'updateOnBrowserResize' : dynamic, updateOnContentResize: dynamic},
                                 callbacks:{
                                     onTotalScroll: function(){scrollFunc();},
                                     onTotalScrollOffset:300
                                 },

                                 scrollButtons:{
                                    scrollSpeed:200,
                                    scrollAmount: 300
                                 },
                                  scrollInertia : 0
                                 });
    return element.find('.mCSB_container');
}

function makeDomHtml(attributes, html, includeStart, includeEnd, objectType) {
    var result = '';
    attributes = undefArg(attributes,{});
    includeStart = undefArg(includeStart,true);
    includeEnd = undefArg(includeEnd,true);
    objectType = undefArg(objectType,'div');

    if(includeStart) {
        result = '<' + objectType;
        for(var key in attributes) {
            if (attributes.hasOwnProperty(key)) {
                var value = attributes[key];
                value = undefArg(value);
                if(value != null) {
                    result += ' ' + key + '="' + value + '"';
                }
            }
        }
        result += '>';
    }

    result += html;

    if(includeEnd) {
        result += '</' + objectType + '>';
    }
    return result;
}

function joinStrings(strs,seperator) {
    strs = undefArg(strs);
    seperator = undefArg(seperator,' ');

    if(strs == null || strs.length == 0) {
        return '';
    }

    var result = '';
    var isFirst = true;
    for(var n = 0;n<strs.length;n++) {
        var todo = undefArg(strs[n]);
        if(todo != null) {
            if(!isFirst) {
                result += seperator;
            } else {
                isFirst = false;
            }

            result += strs[n];
        }
    }
    return result;
}

function makeDiv(classText, id, includeStart, includeEnd) {
    return function(html) {
        return makeDomHtml({'class' : classText, 'id' : id}, html, includeStart, includeEnd);
    }
}
function makeRow(classText, id, includeStart, includeEnd) {
    return function(html) {
        return makeDomHtml({'class' : joinStrings(['row-fluid', classText]), 'id' : id}, html, includeStart, includeEnd);
    }
}

function makeImage(imageUrl, altText, hoverText, classText, id) {
    return makeDomHtml({'class' : classText, 'id' : id, 'src' : imageUrl, 'alt' : altText, 'title' : hoverText}, '', true, true, 'img');
}

function makeHyperlink(url, contents, target) {
    return '<a href="' + url + '" target="' + target + '">' + contents + '</a>';
}

function makeParagraph() {
    return function(html) {
        return '<p>' + html + '</p>'
    }
}

function undefArg(arg, defaultValue, call) {
    if (typeof defaultValue === "undefined") {
        defaultValue = null;
    }
    if (typeof call === "undefined") {
        call = false;
    }
    if (typeof arg === "undefined" || arg == null) {
        return defaultValue;
    }
    if(call && isFunction(arg)) {
        arg = arg();
        if (typeof arg === "undefined" || arg == null) {
            return defaultValue;
        } else {
            return arg;
        }
    }
    return arg;
}

function buildUrl(url, arguments) {
    arguments = undefArg(arguments);

    if(arguments == null || arguments.length == 0) {
        return url;
    }

    url += '?';
    var isFirst = true;
    $.each(arguments, function (key, value) {
        if(undefArg(value) != null) {
            if(isFirst) {
                isFirst = false;
            } else {
                url += '&';
            }

            url += key + '=' + value;
        }
    });

    console.info('Built url: ' + url);
    return url;
}

function downloadUrl(url, downloadId) {
    url = url + downloadId;
    downloadId = 'downloadFrame_'+downloadId;

    var frame = $('#'+downloadId);
    if (frame.length == 0) {
        frame = $('<iframe id="' + downloadId + '" class="hidden"/>');
        $(document.body).append(frame);
    }
    frame.attr('src',url);
    console.log('src is ' + url);
}

function setupSpecialButtons(selector, callback) {
    var thisId = selector.attr('id');
    var isRadio = selector.parent().hasClass('custom-buttons-radio');

    callback = undefArg(callback);

    selector.click(function(e){
        var isChecked = selector.hasClass('active');

        if(!isChecked) {
            console.log(thisId + ' was activated');
            selector.addClass('active');

            if(isRadio) {
                selector.addClass('newly-active');

                selector.siblings().each(function(){
                    var siblingId = $(this).attr('id');
                    $(this).removeClass('active');
                    $(this).removeClass('newly-active');
                    callback($(this),false);
                    console.log(siblingId + ' was deactivated');
                })
            }

            callback(selector,true);
        } else {
            if(isRadio) {
                selector.removeClass('newly-active');
            }
        }
    });
}

var sizesPlural = ['Bytes', 'Kilobytes (KB)', 'Megabytes (MB)', 'Gigabytes (GB)', 'Terabytes (TB)'];
var sizesSingle = ['Byte', 'Kilobyte (KB)', 'Megabyte (MB)', 'Gigabyte (GB)', 'Terabyte (TB)'];
function bytesToSize(bytes) {

    if (bytes == 0) {
        return '0';
    } else {
        var aux = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
        var value = Math.round(bytes / Math.pow(1024, aux), 2);

        if(value == 1) {
            return value + ' ' + sizesSingle[aux];
        } else {
            return value + ' ' + sizesPlural[aux];
        }
    }
}

function setupTabs(selector) {
    selector.click(function (e) {
        e.preventDefault();
        $(this).tab('show');
    });
}

function fixStringSize(string, prependStr, idealSize) {
    string = string.toString();

    while(string.length < idealSize) {
        string = prependStr + string;
    }
    return string.slice(-idealSize);
}

function getNiceDateString(dateObject) {
    var dayOfWeek = dateObject.getDay();
    switch(dayOfWeek) {
        case 0:
            dayOfWeek = 'Sunday';
            break;

        case 1:
            dayOfWeek = 'Monday';
            break;

        case 2:
            dayOfWeek = 'Tuesday';
            break;

        case 3:
            dayOfWeek = 'Wednesday';
            break;

        case 4:
            dayOfWeek = 'Thursday';
            break;

        case 5:
            dayOfWeek = 'Friday';
            break;

        case 6:
            dayOfWeek = 'Saturday';
            break;

        default:
            dayOfWeek = '?';
            break;
    }

    var day = fixStringSize(dateObject.getUTCDate(),'0',2);
    var month = fixStringSize(dateObject.getUTCMonth() + 1,'0',2);
    var year = dateObject.getUTCFullYear();

    var seconds = fixStringSize(dateObject.getUTCSeconds(),'0',2);
    var minutes = fixStringSize(dateObject.getUTCMinutes(),'0',2);
    var hours = fixStringSize(dateObject.getUTCHours(),'0',2);

    return dayOfWeek + ' ' + day + '/' + month + '/' + year + ' - ' + hours + ':' + minutes + ':' + seconds;
}

function getNiceDateStringFromEpoch(epoch) {
    return getNiceDateString(new Date(epoch));
}

var CollapsibleEx = function(startShown, accordion, pageElement) {
    var collapsed = !startShown;

    var onShow = function() {
        collapsed = false;
    };

    var onHide = function() {
        collapsed = true;
    };

    pageElement.collapse({toggle : startShown, parent : accordion})
               .on('show', onShow)
               .on('hide', onHide);

    this.x = pageElement;

    this.isCollapsed = function() {
        return collapsed
    };

    this.hide = function() {
        if(!collapsed) {
            pageElement.collapse('hide');
        }
    };

    this.show = function() {
        if(collapsed) {
            pageElement.collapse('show');
        }
    };
};