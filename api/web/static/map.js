var STYLE_ID = 997;

function getTileUrl(cloudKey, server, zoom, x, y) {
    server = undefArg(server, '{s}');
    zoom = undefArg(zoom, '{z}');
    x = undefArg(x, '{x}');
    y = undefArg(y, '{y}');

    return 'http://a.tile.openstreetmap.org/' + zoom + '/' + x + '/' + y + '.png';
}

function setupMap($element, cloudKey, imageView) {
    imageView = undefArg(imageView, false);

    var options = {};

    if(imageView) {
        options['dragging'] = false;
        options['touchZoom'] = false;
        options['scrollWheelZoom'] = false;
        options['doubleClickZoom'] = false;
        options['boxZoom'] = false;
        options['keyboard'] = false;
        options['zoomControl'] = false;
        options['attributionControl'] = false;
        options['inertia'] = false;
    }

    var theMap = L.map($element.get(0),options);

    L.tileLayer( getTileUrl(cloudKey),{   maxZoom: 18,
                                          styleId: STYLE_ID,
                                          attribution: 'Map data &copy; <a href="http://openstreetmap.org">OpenStreetMap</a> contributors' })
                .addTo(theMap);

    return theMap;
}

function forceUpdate(leafletMap) {
    L.Util.requestAnimFrame(leafletMap.invalidateSize,leafletMap,!1,leafletMap._container);
}

function updateOnTabSwitch(tabSelector, leafletMap) {
    $(tabSelector).on('shown', function() {
        forceUpdate(leafletMap);
    });
}

var minBound = null;
var maxBound = null;

function MapFitView(map) {
    var thisObject = this;

    var minBound = null;
    var maxBound = null;

    this.bestFitView = function(enforce) {
        enforce = undefArg(enforce, false);

        if(enforce) {
            $(window).resize(function() {
                thisObject.bestFitView(false);
            });
        }

        var leafletMap = map.leaflet_map;
        if(minBound == null || maxBound == null) {
            leafletMap.fitWorld();
        } else {
            leafletMap.fitBounds([minBound, maxBound]);
        }
        forceUpdate(map.leaflet_map);
    };

    this.updateBounds = function(coord) {
        var newCoord = new Array();
        newCoord.push(coord[0]);
        newCoord.push(coord[1]);
        coord = newCoord;

        if(minBound == null) {
            minBound = coord.slice(0);
        } else {
            if(coord[0] < minBound[0]) {
                minBound[0] = coord[0];
            }
            if(coord[1] < minBound[1]) {
                minBound[1] = coord[1];
            }
        }

        if(maxBound == null) {
            maxBound = coord.slice(0);
        } else {
            if(coord[0] > maxBound[0]) {
                maxBound[0] = coord[0];
            }
            if(coord[1] > maxBound[1]) {
                maxBound[1] = coord[1];
            }
        }
    };
}

function Map(name,cloudKey,useClusters,customClusterMarkerFunc,singleMarkerModeEnabled,defaultInitialiseMap,imageView) {
    useClusters = undefArg(useClusters, false);
    customClusterMarkerFunc = undefArg(customClusterMarkerFunc);
    singleMarkerModeEnabled = undefArg(singleMarkerModeEnabled,false);
    defaultInitialiseMap = undefArg(defaultInitialiseMap,true);
    imageView = undefArg(imageView, false); // map acts like an image and is not scrollable.

    this.name = name.attr('id');

    this.leaflet_map = setupMap(name, cloudKey, imageView);

    if(defaultInitialiseMap) {
        this.leaflet_map.setView([51.505, -0.09], 1);
    }

    var objects = null;

    var customLayers = {};

    var getNewLayerGroup = function() {
        if(useClusters) {
            return new L.MarkerClusterGroup({showCoverageOnHover : false, iconCreateFunction: customClusterMarkerFunc, singleMarkerMode : singleMarkerModeEnabled});
        } else {
            return L.layerGroup();
        }
    };

    this.addLayersTo = null;
    if(useClusters) {
        this.addLayersTo = getNewLayerGroup();
        this.leaflet_map.addLayer(this.addLayersTo);
    } else {
        this.addLayersTo = this.leaflet_map;
    }

    var setupObjects = function() {
        objects = undefArg(objects,null);
        if(objects == null) {
            objects = new ObjectMap();
        }
        return objects;
    };

    this.addToLayerGroup = function(groupName, item, itemHashKey) {
        itemHashKey = undefArg(itemHashKey);
        if(itemHashKey != null) {
            setupObjects();
            if(!objects.add(itemHashKey,item)) {
                return false;
            }
        }

        var group;
        if(!(groupName in customLayers)) {
            group = getNewLayerGroup();
            customLayers[groupName] = group;
            group.addTo(this.leaflet_map);
        } else {
            var originalGroup = customLayers[groupName];
            if(originalGroup === true || originalGroup === false) {
                group = getNewLayerGroup();
                customLayers[groupName] = group;

                if(originalGroup === true) {
                    group.addTo(this.leaflet_map);
                }
            } else {
                group = originalGroup;
            }
        }
        group.addLayer(item);
        return true;
    };

    this.hideLayerGroup = function(groupName) {
        if(groupName in customLayers) {
            var layer = customLayers[groupName];
            if(layer !== false && layer !== true) {
                this.leaflet_map.removeLayer(layer);
            } else {
                customLayers[groupName] = false;
            }
            return true;
        } else {
            customLayers[groupName] = false;
            return false;
        }
    };

    this.clearMap = function() {
        var keyList = [];
        for(var groupName in customLayers) {
            keyList.push(groupName);
        }
        for(var i in keyList) {
            this.clearLayerGroup(keyList[i]);
        }
        this.addLayersTo.clearLayers();
    };

    this.clearLayerGroup = function(groupName) {
        if(groupName in customLayers) {
            var layer = customLayers[groupName];
            if(layer !== true && layer !== false) {
                layer.clearLayers();
            }
        }
    };

    this.showLayerGroup = function(groupName) {
        if(groupName in customLayers) {
            var layer = customLayers[groupName];
            if(layer !== false && layer !== true) {
                this.leaflet_map.addLayer(layer);
            } else {
                customLayers[groupName] = true;
            }
            return true;
        } else {
            customLayers[groupName] = true;
            return false;
        }
    };

    this.addItem = function(item) {
        this.addLayersTo.addLayer(item);
    };

    this.removeItem = function(item) {
        this.addLayersTo.removeLayer(item);
    };

    this.add = function(itemHashKey,item) {
        setupObjects();
        if(objects.add(itemHashKey,item) == true) {
            this.addLayersTo.addLayer(item);
        }
    };

    this.remove = function(itemHashKey) {
        setupObjects();
        var result = objects.remove(itemHashKey);
        if (!(result == null)){
            this.addLayersTo.removeLayer(result);
        }
    };
}