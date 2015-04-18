function MapControl(map)
{
    this.control_name = map.name;
    this.message_func = function (operations,jsonData) {
        if(processDocumentOperations(operations, jsonData)) {
            return;
        }

        var newItem = null;

        // Remove item operations are different, so we return early.
        if(jsonData.op == operations.REMOVE_ITEM) {
            //console.debug("REMOVE_ITEM operation received for hash key " + jsonData.hashKey);
            map.remove(jsonData.hashKey);
            return
        }

        // Load properties, these set things like colour.
        var properties = null;
        if(jsonData.properties)
        {
            properties = $.parseJSON(jsonData.properties);
            //console.debug("Properties loaded: " + jsonData.properties);
        }

        // Create object of correct type.
        switch(jsonData.op)
        {
            case operations.ADD_MARKER:
                //console.debug("ADD_COORD operation received " + jsonData.coord);
                newItem = L.marker(jsonData.coord, properties);
                break;

            case operations.ADD_LINE:
                //console.debug("ADD_LINE operation received " + jsonData.coords);
                newItem = L.polyline(jsonData.coords, properties);
                break;

            default:
                console.error("Invalid operation " + jsonData.op);
        }

        newItem.properties = properties;

        // Add popup.
        if(jsonData.popupText) {
            //console.debug("Adding popup: " + jsonData.popupText);
            newItem.bindPopup(jsonData.popupText);
        }

        // Add object to map.
        var hashKey = jsonData.hashKey;

        if('custom_layers' in properties) {
            var customLayers = properties['custom_layers'];
            $(customLayers).each(function() {
                 map.addToLayerGroup(this,newItem,hashKey);
            });
        } else {
            map.add(hashKey,newItem);
        }
    };
}