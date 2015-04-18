function validateProjection(projection) {
    projection = undefArg(projection);
    if(projection != null &&
       projection != 'name-only') {
        var error = 'Invalid projection type: ' + projection;
        console.error(error);
        return null;
    }
    return projection
}

function validateType(type) {
    type = undefArg(type);
    if(type != 'tweet' &&
       type != 'user') {
        console.error('Invalid cache query type: ' + type);
        return null;
    }
    return type;
}

function queryCache(type, instance, startEpoch, endEpoch, placeId, providerId, followee, page, onSuccess, onFail, onAlways, projection) {
    type = validateType(type);
    projection = validateProjection(projection);

    var urlArgs =  {'type' : type,
                    'page' : page,
                    'start_epoch' : startEpoch,
                    'end_epoch' : endEpoch,
                    'place_id' : placeId,
                    'provider_id' : providerId,
                    'followee' : followee,
                    'projection_type' : projection};
    var urlToLoadFrom = buildUrl('/instance/'+instance+'/cached_tweets',urlArgs);
    console.info('Querying URL: ' + urlToLoadFrom);
    getPage(urlToLoadFrom, onSuccess, onFail, onAlways);
}

function queryInfluenceCache(instance, startEpoch, endEpoch, sourcePlaceId, sourceProviderId, onSuccess, onFail, onAlways) {
    startEpoch = undefArg(startEpoch);
    endEpoch = undefArg(endEpoch);

    var urlArgs =  {'source_place_id' : sourcePlaceId, 'source_provider_id' : sourceProviderId};

    if(startEpoch != null) {
        urlArgs['start_epoch'] = startEpoch;
    }
    if(endEpoch != null) {
        urlArgs['end_epoch'] = endEpoch;
    }

    var urlToLoadFrom = buildUrl('/instance/'+instance+'/influence',urlArgs);
    console.info('Querying URL: ' + urlToLoadFrom);
    getPage(urlToLoadFrom, onSuccess, onFail, onAlways);
}

function PagedCacheQuery(pageElement, processDataFunc, type, instance, startEpoch, endEpoch, placeId, providerId, followee, projection) {
    var currentPage = 0;
    var isWaitingForLoad = false;
    var resetIsQueued = false;
    var dataCache = null;

    this.reset = function() {
        resetIsQueued = true;
        currentPage = 0;
        isWaitingForLoad = false;
    };

    this.setPageElement = function(newPageElement) {
        pageElement = newPageElement
    };

    this.setEpochRange = function(p_startEpoch, p_endEpoch) {
        this.reset();
        startEpoch = p_startEpoch;
        endEpoch = p_endEpoch;
    };

    this.setStartEpoch = function(p_startEpoch) {
        this.reset();
        startEpoch = p_startEpoch;
    };

    this.setEndEpoch = function(p_endEpoch) {
        this.reset();
        endEpoch = p_endEpoch;
    };

    var _hardReset = function() {
        pageElement.empty();
        dataCache = null;
    };

    var onSuccess = function(data) {
        data = undefArg(data);
        if(data != null) {
            data = data['json'];
        }

        if(resetIsQueued) {
            _hardReset();
            resetIsQueued = false;
        }

        if(data == null) {
            console.warn('Null data received, need to retry that page');
            isWaitingForLoad = false;
            return;
        }

        if(data.length == 0) {
            console.info('No more data');
            return;
        }

        if(dataCache != null) {
            dataCache = dataCache.concat(data);
        } else {
            dataCache = data;
        }

        currentPage++;
        isWaitingForLoad = false;

        processDataFunc(data, pageElement);
    };

    var onFailure = function(data) {
        if(resetIsQueued) {
            _hardReset();
            resetIsQueued = false;
        }
    };

    this.setProcessDataFunc = function(newFunc) {
        pageElement.empty();

        processDataFunc = newFunc;

        if(dataCache != null) {
            processDataFunc(dataCache, pageElement);
        }
    };

    this.loadNextPage = function() {
        if(!isWaitingForLoad) {
            isWaitingForLoad = true;
            queryCache(type, instance, startEpoch, endEpoch, placeId, providerId, followee, currentPage, onSuccess, onFailure, null, projection);
        }
    };
}

function PagedScroller(pageCacheQuery, scrollbarElement, requiredDistanceFromBottom, updateFrequency, onUpdateFunc) {
    var startEpoch;
    var endEpoch;
    var sliderChanged = false;

    onUpdateFunc = undefArg(onUpdateFunc);

    this.setEpochRange = function(p_startEpoch, p_endEpoch) {
        startEpoch = p_startEpoch;
        endEpoch = p_endEpoch;
        sliderChanged = true;
    };

    // Update display of tweets every few milliseconds.
    if(updateFrequency != null) {
        setInterval(function(){
            if(sliderChanged) {
                pageCacheQuery.setEpochRange(startEpoch, endEpoch);
                pageCacheQuery.loadNextPage();
                if(onUpdateFunc != null) {
                    onUpdateFunc(startEpoch, endEpoch);
                }
                sliderChanged = false;
            }
        },updateFrequency);
    }

    // load data during scrolling.
    this.scrollableDiv = applyScrollbar($(scrollbarElement), function() {
        pageCacheQuery.loadNextPage();
    });
}

function makeImageFromUserData(imageClass, embedHyperlink, target) {
    target = undefArg(target, '_self');
    embedHyperlink = undefArg(embedHyperlink, true);

    return function(row) {
        var userId = row[0];
        var userName = row[1];
        var imageUrl = row[2];
        var onClickNavigateTo = row[3];

        var result = makeImage(imageUrl, userName, userName, imageClass);
        if(embedHyperlink) {
            result = makeHyperlink(onClickNavigateTo,result,target);
        }
        return result;
    }
}

function makeTextFromUserData(className, embedHyperlink, target) {
    target = undefArg(target, '_self');
    embedHyperlink = undefArg(embedHyperlink, true);
    className = undefArg(className);

    return function(row) {
        var userId = row[0];
        var userName = row[1];
        var imageUrl = row[2];
        var onClickNavigateTo = row[3];

        var result = '<p image_url="' + imageUrl + '"';
        if(className != null) {
            result += ' class="' + className + '"';
        }
        result += '>' + userName + '</p>';

        if(embedHyperlink) {
            result = makeHyperlink(onClickNavigateTo,result,target);
        }
        return result;
    }
}

function makeImageFromUserDataProcess(imageClass) {
    return function(dataElement) {
        return makeImageFromUserData(imageClass)(dataElement);
    }
}

function processCacheDataFuncUser(rowSize, processDataElementFunc, elementDivClass, afterPageElementUpdated) {
    var startRowFunc = makeRow(null,null,true,false);
    var endRowFunc = makeRow(null,null,false,true);

    rowSize = undefArg(rowSize,1);
    afterPageElementUpdated = undefArg(afterPageElementUpdated);

    return function(data, pageElement) {
        var result = '';
        var row = '';

        var waitingToCloseRow = false;
        var forceNewRow = false;

        var rowOffset = 0;

        var lastRow = pageElement.find('div.row-fluid:last');
        if(lastRow != null && lastRow.length > 0) {
            lastRow = $(lastRow[0]);

            var elements = lastRow.find('div');
            var elementsLength = elements.length;

            if(elementsLength != rowSize) {
                rowOffset = elementsLength;
                row += lastRow.html();
                lastRow.remove();
                forceNewRow = true;
            }
        }

        var nOffset = rowOffset;
        for(var n = 0;n<data.length;n++, nOffset++) {
            var newRow = nOffset % rowSize == 0;

            if(newRow || forceNewRow) {
                forceNewRow = false;

                if(waitingToCloseRow) {
                    row = endRowFunc(row);
                    result += row;
                    row = '';
                } else {
                    waitingToCloseRow = true;
                }

                row = startRowFunc(row);
            }

            row += makeDiv(elementDivClass)(processDataElementFunc(data[n]));
        }

        if(waitingToCloseRow) {
            result += endRowFunc(row);
            waitingToCloseRow = false;
        }

        pageElement.append(result);

        if(afterPageElementUpdated != null) {
            afterPageElementUpdated(pageElement);
        }
    };
}