var RECTANGLE_TYPE = 1;
var MARKER_TYPE = 2;

function updateElementWithMapDrawings(itemList, pageElement){
    var results = [];
    for(var n = 0;n<itemList.length;n++){
        var displayType = itemList[n][0];
        var entityType = itemList[n][1];
        var item = itemList[n][2];
        var extraData = itemList[n][3];

        var coords = new Array();
        if(displayType == RECTANGLE_TYPE) {
            var bounds = item.getBounds();
            var ne = bounds.getNorthEast();
            var sw = bounds.getSouthWest();

            // south, west, east, north
            coords.push(sw.lat);
            coords.push(sw.lng);
            coords.push(ne.lat);
            coords.push(ne.lng);
        } else if(displayType == MARKER_TYPE) {
            var coord = item.getLatLng();
            coords.push(coord.lat);
            coords.push(coord.lng);
        } else {
            alert('invalid map item type');
        }

        var subResults = new Array();
        subResults.push(displayType);
        subResults.push(entityType);
        subResults.push(coords);
        subResults.push(extraData);
        results.push(subResults);
    }

    $(pageElement).val(JSON.stringify(results));
}

function processMapDrawings(regionsList, processRegionFunc) {
    $(regionsList).each(function() {
        var displayType = this[0];
        var entityType = this[1];
        var coords = this[2];
        var extraData = this[3];
        processRegionFunc(displayType, entityType, coords, extraData);
    });
}

function DrawableMap(map, regionTextObject, beginDrawingButton, deleteLastDrawingButton, onItemDrawFunc, onItemRemoveFunc) {
    regionTextObject = undefArg(regionTextObject);
    beginDrawingButton = undefArg(beginDrawingButton);
    deleteLastDrawingButton = undefArg(deleteLastDrawingButton);
    onItemDrawFunc = undefArg(onItemDrawFunc);
    onItemRemoveFunc = undefArg(onItemRemoveFunc);
    this.map = map;

    var startPosition = null;
    var drawingInProgressRectangle = null;
    var rectangleList = [];
    var updateRegionsTextObject = function() {
        if(regionTextObject != null) {
            updateElementWithMapDrawings(rectangleList, regionTextObject);
        }
    };

    var isDrawingInProgress = false;

    var thisObject = this;

    if(beginDrawingButton != null) {
        beginDrawingButton.click(function() {
            isDrawingInProgress = !isDrawingInProgress;

            if(isDrawingInProgress) {
                $(this).attr('disabled', 'disabled');
            }

            return false;
        });
    }

    var removeItemFromMap = function(displayType, entityType, item) {
        map.removeItem(item);

        if(onItemRemoveFunc != null) {
            onItemRemoveFunc(displayType, entityType, item);
        }

        if(rectangleList.length == 0) {
            if(deleteLastDrawingButton != null) {
                deleteLastDrawingButton.attr('disabled', 'disabled');
            }
        }

        updateRegionsTextObject();
    };

    this.deleteLastDrawing = function() {
        var rectData = rectangleList.pop();
        var displayType = rectData[0];
        var entityType = rectData[1];
        var item = rectData[2];

        removeItemFromMap(displayType,entityType,item);
    };

    if(deleteLastDrawingButton != null) {
        deleteLastDrawingButton.click(function() {
            thisObject.deleteLastDrawing();
            return false;
        });
    }

    var addItemToMap = function(itemType, item, mapModeOverride) {
        mapModeOverride = undefArg(mapModeOverride);

        map.addItem(item);

        var subArray = new Array();
        subArray.push(itemType);

        var entityId;
        if(onItemDrawFunc != null) {
            entityId = onItemDrawFunc(itemType, item, mapModeOverride);
        } else {
            entityId = 0;
        }

        subArray.push(entityId);
        subArray.push(item);
        subArray.push(item.extraData);

        rectangleList.push(subArray);
        updateRegionsTextObject();

        if(deleteLastDrawingButton != null) {
            deleteLastDrawingButton.removeAttr('disabled');
        }
    };

    var rectangleOptions = null;
    this.setDrawRectangleOptions = function(options) {
        rectangleOptions = options;
    };

    var mapFitView = new MapFitView(this.map);

    this.bestFitView = function(enforce) {
        mapFitView.bestFitView(enforce);
    };

    this.addRectangleArea = function(startPos, endPos, extraData, mapModeOverride) {
        extraData = undefArg(extraData,{});
        mapModeOverride = undefArg(mapModeOverride);

        var rect = new L.rectangle([startPos, endPos], rectangleOptions);
        rect.extraData = extraData;
        addItemToMap(RECTANGLE_TYPE, rect, mapModeOverride);

        mapFitView.updateBounds(startPos);
        mapFitView.updateBounds(endPos);
    };

    this.addMarker = function(coord, extraData, mapModeOverride) {
        extraData = undefArg(extraData);
        mapModeOverride = undefArg(mapModeOverride);

        var marker = L.marker(coord);
        marker.extraData = extraData;
        addItemToMap(MARKER_TYPE, marker, false);

        mapFitView.updateBounds(coord);
    };

    map.leaflet_map.on('mouseup', function(e) {
        if(isDrawingInProgress) {
            if(startPosition == null) {
                startPosition = e.latlng;
            } else {
                var end = e.latlng;
                thisObject.addRectangleArea(startPosition, end, null);
                startPosition = null;

                if(drawingInProgressRectangle != null) {
                    map.removeItem(drawingInProgressRectangle);
                    drawingInProgressRectangle = null;
                }

                if(beginDrawingButton != null) {
                    beginDrawingButton.removeAttr('disabled');
                }
                isDrawingInProgress = false;
            }
        }
    });

    map.leaflet_map.on('mousemove', function(e) {
        if(startPosition != null) {
            if(drawingInProgressRectangle != null) {
                map.removeItem(drawingInProgressRectangle);
            }
            drawingInProgressRectangle = new L.rectangle([startPosition, e.latlng],rectangleOptions);
            map.addItem(drawingInProgressRectangle);
        }
    });
}