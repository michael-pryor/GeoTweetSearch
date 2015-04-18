function Table(name, onNewRowFunc, onNewCellFunc) {
    onNewRowFunc = undefArg(onNewRowFunc);
    onNewCellFunc = undefArg(onNewCellFunc);

    this.name = name;

    var table = document.getElementById(name);

    this.object_map = new ObjectMap();

    this.numRows = function() {
        return table.rows.length;
    };

    var createAndPopulateCell = function(cellData, forceHeader) {
        var header = cellData[4];

        var cell;
        if(forceHeader || header) {
            cell = document.createElement("th");
        } else {
            cell = document.createElement("td");
        }

        return populateCell(cell, cellData);
    };

    var populateCell = function(cellObject, cellData) {
        var cellHtml = cellData[0];
        var cellWidth = cellData[1];
        var cellHeight = cellData[2];
        var className = cellData[3];
        setElementInnerHtml(cellObject, cellHtml);

        if(cellWidth != null) cellObject.style.width = cellWidth;
        if(cellHeight != null) cellObject.style.height = cellHeight;
        if(className != null) cellObject.className = className;
        return cellObject;
    };

    this.add = function(itemHashKey,cells,index,updateMode) {
        if(typeof(index)==='undefined') index = 0;

        if(index > this.numRows()) {
            index = -1
        }

        if(this.object_map.contains(itemHashKey) == false) {
            var row = table.insertRow(index);
            this.object_map.add(itemHashKey,row);

            for(var i = 0; i < cells.length; i++){
                var cellData = cells[i];
                var cellObj = createAndPopulateCell(cellData,false);
                row.appendChild(cellObj);
                if(onNewCellFunc != null) {
                    onNewCellFunc(cellObj, true);
                }
            }
            if(onNewRowFunc != null) {
                onNewRowFunc(row, true);
            }
        } else {
            if(updateMode) {
                var row = this.object_map.get(itemHashKey);
                var oldCells = row.cells;

                for(var i = 0;i < cells.length;i++) {
                    var cellData = cells[i];
                    populateCell(oldCells[i],cellData);
                    if(onNewCellFunc != null) {
                        onNewCellFunc(oldCells[i], false);
                    }
                }
                if(onNewRowFunc != null) {
                    onNewRowFunc(row, false);
                }
                console.info("Updated cell");
            } else {
                console.error("Failed to add row, row already exists: " + itemHashKey);
            }
        }
    };

    this.addToHeader = function(cells) {
        var header = table.createTHead();
        var row = header.insertRow(0);
        for(var i = 0; i < cells.length; i++){
            var cellData = cells[i];
            row.appendChild(createAndPopulateCell(cellData,true));
        }
    };

    this.remove = function(itemHashKey) {
        var row = this.object_map.remove(itemHashKey);
        if(row != null) {
            table.deleteRow(row.rowIndex);
        }
    };
}

function TableControl(table)
{
    this.control_name = table.name;
    this.message_func = function (operations,jsonData) {
        if(processDocumentOperations(operations, jsonData)) {
            return;
        }

        var newItem = null;
        var hashKey = jsonData.hashKey;

        // Remove item operations are different, so we return early.
        if(jsonData.op == operations.REMOVE_ITEM) {
            console.debug("REMOVE_ITEM operation received for hash key " + jsonData.hashKey);
            table.remove(hashKey);
            return;
        }

        // Create object of correct type.
        switch(jsonData.op)
        {
            case operations.ADD_ROW:
                console.debug("ADD_ROW operation received " + jsonData.cells);

                var rowIndex = 1;
                if(jsonData.rowIndex) {
                    rowIndex = jsonData.rowIndex;
                }

                table.add(hashKey,jsonData.cells,rowIndex,false);
                break;

            case operations.UPDATE_ROW:
                console.debug("UPDATE_ROW operation received " + jsonData.cells);

                var rowIndex = 1;
                if(jsonData.rowIndex) {
                    rowIndex = jsonData.rowIndex;
                }

                table.add(hashKey,jsonData.cells,rowIndex,true);
                break;

            case operations.SET_HEADER:
                console.debug("SET_HEADER operation received " + jsonData.cells);
                table.addToHeader(jsonData.cells);
                break;

            default:
                console.error("Invalid operation " + jsonData.op);
        }

    };
}