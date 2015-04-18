var INFLUENCE_SOURCE = 1;
var GEOGRAPHICAL_FILTER = 2;
var INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER = 3;

var geographicalFilterButtonBaseText = 'Geographical Filter';

var yellowRectangle = {color: '#FFFF00'};
var redRectangle = {color : '#FF0000'};
var greenRectangle = {color : '#00FF00'};

function DrawableMapInstance(map,
                             regionTextObject,
                             beginDrawingButton,
                             deleteLastDrawingButton,
                             buttonGeographicalFilter,
                             buttonInfluenceSource,
                             maxGeographicalRegions,
                             onGeographicalFilterButtonActive,
                             onInfluenceSourceButtonActive,
                             onGeographicFilterChange,
                             popupsEnabled) {
    buttonGeographicalFilter = undefArg(buttonGeographicalFilter);
    buttonInfluenceSource = undefArg(buttonInfluenceSource);
    onGeographicalFilterButtonActive = undefArg(onGeographicalFilterButtonActive);
    onInfluenceSourceButtonActive = undefArg(onInfluenceSourceButtonActive);
    onGeographicFilterChange = undefArg(onGeographicFilterChange);
    popupsEnabled = undefArg(popupsEnabled, true);

    var totalAvailableGeographicalFilters = maxGeographicalRegions;
    var numConsumedGeographicalFilters = 0;
    var lastNumGeographicFilters = null;

    var isSelectDrawTypeButtonsEnabled = buttonGeographicalFilter && buttonInfluenceSource;

    // This lets us ensure one 'checkbox' is always checked.
    //
    // Some nasty hacking in this! The issue is that bootstrap doesn't
    // update the active class until AFTER this callback is called.
    // We can figure out what it will be when we have two buttons in the group
    // but with more this will fail.
    if(isSelectDrawTypeButtonsEnabled) {
        var isInfluenceSourceButtonActive = false;
        var isGeographicalFilterButtonActive = true;
        buttonGeographicalFilter.click(function() {
            if($(this).hasClass('active')) {
                if(!buttonInfluenceSource.hasClass('active')) {
                    buttonInfluenceSource.addClass('active');
                    isInfluenceSourceButtonActive = true;
                    if(onInfluenceSourceButtonActive != null) {
                        onInfluenceSourceButtonActive();
                    }
                }
                isGeographicalFilterButtonActive = false;
            } else {
                isGeographicalFilterButtonActive = true;
                if(onGeographicalFilterButtonActive != null) {
                    onGeographicalFilterButtonActive();
                }
            }
        });
        buttonInfluenceSource.click(function() {
            if($(this).hasClass('active')) {
                if(!buttonGeographicalFilter.hasClass('active')) {
                    buttonGeographicalFilter.addClass('active');
                    isGeographicalFilterButtonActive = true;
                    if(onGeographicalFilterButtonActive != null) {
                        onGeographicalFilterButtonActive();
                    }
                }
                isInfluenceSourceButtonActive = false;
            } else {
                isInfluenceSourceButtonActive = true;
                if(onInfluenceSourceButtonActive != null) {
                    onInfluenceSourceButtonActive();
                }
            }
        });

        this.getMapMode = function() {
            if(isGeographicalFilterButtonActive) {
                if(!isInfluenceSourceButtonActive) {
                    return GEOGRAPHICAL_FILTER;
                } else {
                    return INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER;
                }
            } else {
                return INFLUENCE_SOURCE;
            }
        };
        var getMapMode = this.getMapMode;

        var updateGeographicFiltersButton = function() {
            if(lastNumGeographicFilters != numConsumedGeographicalFilters) {
                lastNumGeographicFilters = numConsumedGeographicalFilters;

                var numRemaining = totalAvailableGeographicalFilters - numConsumedGeographicalFilters;

                buttonGeographicalFilter.html(geographicalFilterButtonBaseText + ' ('+numRemaining+')');
                if(numRemaining == 0) {
                    buttonGeographicalFilter.attr('disabled','disabled');
                    buttonGeographicalFilter.click();
                } else {
                    buttonGeographicalFilter.removeAttr('disabled');
                }

                if(onGeographicFilterChange != null) {
                    onGeographicFilterChange(numConsumedGeographicalFilters);
                }
            }
        };
        updateGeographicFiltersButton();

        var onItemRemoveFunc = function(itemType, entityId, item) {
            if(entityId == GEOGRAPHICAL_FILTER || entityId == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
                numConsumedGeographicalFilters--;
                updateGeographicFiltersButton();
            }
        };

        this.getNumGeographicFiltersRemaining = function() {
            return totalAvailableGeographicalFilters - numConsumedGeographicalFilters
        };

        this.getNumGeographicFiltersUsed = function() {
            return numConsumedGeographicalFilters
        };
    }

    var getPopup = function(placeName, mode) {
        var popup = '';
        if(mode == GEOGRAPHICAL_FILTER) {
            popup += 'Geographical Filter';
        } else if(mode == INFLUENCE_SOURCE) {
            popup += 'Influence Source';
        } else if(mode == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
            popup += 'Influence Source and Geographical Filter';
        }
        popup = '<b>' + popup + '</b><br>' + placeName;
        return popup;
    };

    var onItemDrawFunc = function(itemType, item, mapMode) {
        if(mapMode == null) {
            if(undefArg(getMapMode) == null) {
                return 0;
            }

            mapMode = getMapMode();
        }

        var extraData = undefArg(item.extraData);
        var placeName = undefArg(item.extraData['placeName']);

        if(itemType == RECTANGLE_TYPE) {
            var bounds = item.getBounds();
            var ne = bounds.getNorthEast();
            var sw = bounds.getSouthWest();
            var dp = 2;

            // Was drawn by user manually so has no place name.
            if(placeName == null) {
                placeName = 'SW: (' + sw.lat.toFixed(dp) + ', ' + sw.lng.toFixed(dp) + ')<br>NE: (' + ne.lat.toFixed(dp) + ', ' + ne.lng.toFixed(dp) + ')';
            } else {
                // Influence source is done by marker instead of box unless drawn manually.
                if(mapMode == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
                    mapMode = GEOGRAPHICAL_FILTER;
                }
            }

            if(mapMode == GEOGRAPHICAL_FILTER || mapMode == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
                numConsumedGeographicalFilters++;

                if(isSelectDrawTypeButtonsEnabled) {
                    updateGeographicFiltersButton();
                }
            }

            if(mapMode == GEOGRAPHICAL_FILTER) {
                item.setStyle(greenRectangle);
            } else if(mapMode == INFLUENCE_SOURCE) {
                item.setStyle(redRectangle);
            } else if(mapMode == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
                item.setStyle(yellowRectangle);
            }

        } else if(itemType == MARKER_TYPE) {
            // markers always represent influence sources.
            mapMode = INFLUENCE_SOURCE;
        }

        if(placeName != null && popupsEnabled) {
            item.bindPopup(getPopup(placeName, mapMode));
        }

        return mapMode;
    };

    this.drawableMap = new DrawableMap(map, regionTextObject, beginDrawingButton, deleteLastDrawingButton, onItemDrawFunc, onItemRemoveFunc);
    var drawableMap = this.drawableMap;

    if(isSelectDrawTypeButtonsEnabled) {
        var setRectangleFunc = function() {
            var mapMode = getMapMode();
            if(mapMode == INFLUENCE_SOURCE) {
                drawableMap.setDrawRectangleOptions(redRectangle);
            } else if(mapMode == GEOGRAPHICAL_FILTER) {
                drawableMap.setDrawRectangleOptions(greenRectangle);
            } else {
                drawableMap.setDrawRectangleOptions(yellowRectangle);
            }
        };
        buttonGeographicalFilter.click(setRectangleFunc);
        buttonInfluenceSource.click(setRectangleFunc);

        // default enabled.
        buttonGeographicalFilter.click();
    }

    this.loadData = function(theDataString) {
        processMapDrawings(theDataString, function(displayType, entityType, coords, extraData) {
            if(displayType == RECTANGLE_TYPE) {
                drawableMap.addRectangleArea([coords[0],coords[1]],[coords[2],coords[3]],extraData,entityType);
            } else if(displayType == MARKER_TYPE) {
                if(entityType == INFLUENCE_SOURCE || entityType == INFLUENCE_SOURCE_AND_GEOGRAPHICAL_FILTER) {
                    drawableMap.addMarker([coords[0],coords[1]],extraData,entityType);
                }
            }
        });
    };

}
