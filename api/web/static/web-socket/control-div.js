function DivTable(name, maxLength, removePositionP, onNewRowFunc, onNewCellFunc, applyToSelector) {
    maxLength = undefArg(maxLength);
    removePositionP = undefArg(removePositionP,'last');
    onNewRowFunc = undefArg(onNewRowFunc);
    onNewCellFunc = undefArg(onNewCellFunc);
    applyToSelector = undefArg(applyToSelector);

    var removePosition = 'div.row-fluid:' + removePositionP;

    this.name = name;
    this.maxLength = maxLength;

    var createAndPopulateDiv = function(cellData, hashKey) {
        var div = document.createElement("div");
        div.setAttribute('id',hashKey);
        return populateDiv(div, cellData);
    };

    var populateDiv = function(divObject, data) {
        var cellHtml = data[0];
        var className = data[1];
        setElementInnerHtml(divObject, cellHtml);

        if(className != null) divObject.className = className;
        return divObject;
    };

    this.getContentsName = function() {
        return name+'_contents'
    };

    this.getHeaderName = function() {
        return name+'_header'
    };

    var headerDiv = document.getElementById(this.getHeaderName());
    var contentsDiv = document.getElementById(this.getContentsName());
    var $contentsDiv = $('#' + this.getContentsName());
    if(applyToSelector != null) {
        console.log(applyToSelector);
        $contentsDiv = $contentsDiv.find(applyToSelector);
        contentsDiv = $contentsDiv[0];
    }

    if(contentsDiv == null) {
        alert('Could not find element with name: ' + this.getContentsName());
    }


    this.object_map = new ObjectMap();

    this.add = function(itemHashKey,cells,index,updateMode,rowClass) {
        if(typeof(index)==='undefined') index = 0;

        if(!this.object_map.contains(itemHashKey)) {
            var row = createAndPopulateDiv(['',rowClass],'div_row');
            this.object_map.add(itemHashKey,row);

            for(var i = 0; i < cells.length; i++){
                var cellData = cells[i];
                var cellObj = createAndPopulateDiv(cellData,'div_'+itemHashKey);
                row.appendChild(cellObj);
                if(onNewCellFunc != null) {
                    onNewCellFunc(cellObj, true);
                }
            }

            var currentRows = contentsDiv.childNodes;
            var numCurrentRows = currentRows.length;

            if(maxLength != null && numCurrentRows + 1 > maxLength) {
                $(contentsDiv).find(removePosition).remove();
            }

            if(index == -1 || index > numCurrentRows) {
                contentsDiv.appendChild(row);
            } else {
                var currentNode = currentRows[index];

                // internet explorer doesn't like insertBefore without a valid currentNode.
                currentNode = undefArg(currentNode,null);
                if(currentNode == null) {
                    contentsDiv.appendChild(row);
                } else {
                    contentsDiv.insertBefore(row, currentNode);
                }
            }

            if(onNewRowFunc != null) {
                onNewRowFunc(row, true);
            }

        } else {
            if(updateMode) {
                var row = this.object_map.get(itemHashKey);
                var oldCells = row.childNodes;

                for(var i = 0;i < cells.length;i++) {
                    var cellData = cells[i];
                    populateDiv(oldCells[i],cellData);
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

    this.addToHeader = function(cells,rowClass) {
        if(headerDiv == null) {
            alert('Could not find element with name: ' + this.getHeaderName());
        }

        var row = createAndPopulateDiv(['',rowClass],'div_header_row');

        for(var i = 0; i < cells.length; i++){
            var cellData = cells[i];
            row.appendChild(createAndPopulateDiv(cellData,'div_header'));
        }
        headerDiv.appendChild(row);
    };

    this.remove = function(itemHashKey) {
        var row = this.object_map.remove(itemHashKey);
        if(row != null) {
            contentsDiv.removeChild(row);
        }
    };
}

function DivControl(mainDiv)
{
    this.control_name = mainDiv.name;
    this.message_func = function (operations,jsonData) {
        if(processDocumentOperations(operations, jsonData)) {
            return;
        }

        var newItem = null;
        var hashKey = jsonData.hashKey;

        // Remove item operations are different, so we return early.
        if(jsonData.op == operations.REMOVE_ITEM) {
            //console.debug("REMOVE_ITEM operation received for hash key " + jsonData.hashKey);
            mainDiv.remove(hashKey);
            return;
        }

        // Create object of correct type.
        switch(jsonData.op)
        {
            case operations.ADD_ROW:
                //console.debug("ADD_ROW operation received " + jsonData.cells);

                var rowIndex = 0;
                if(jsonData.rowIndex) {
                    rowIndex = jsonData.rowIndex;
                }

                mainDiv.add(hashKey,jsonData.cells,rowIndex,false,jsonData.rowClass);
                break;

            case operations.UPDATE_ROW:
                //console.debug("UPDATE_ROW operation received " + jsonData.cells);

                var rowIndex = 0;
                if(jsonData.rowIndex) {
                    rowIndex = jsonData.rowIndex;
                }

                mainDiv.add(hashKey,jsonData.cells,rowIndex,true,jsonData.rowClass);
                break;

            case operations.SET_HEADER:
                //console.debug("SET_HEADER operation received " + jsonData.cells);
                mainDiv.addToHeader(jsonData.cells, jsonData.rowClass);
                break;

            default:
                console.error("Invalid operation " + jsonData.op);
        }

    };
}

function toggleDivScrollbar(divHeader, divContents) {
    toggleScrollbarY(divContents);
    toggleScrollbarY(divHeader);
}

function toggleDivScrollbarByName(divHeaderName, divContentsName) {
    toggleDivScrollbar(document.getElementById(divHeaderName),document.getElementById(divContentsName));
}