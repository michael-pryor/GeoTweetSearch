function processDocumentOperations(operations, jsonData)
{
    switch(jsonData.op) {
        case operations.SET_ELEMENT_INNER_HTML:
            //console.debug("SET_ELEMENT_INNER_HTML operation received " + jsonData.html);

            var element = document.getElementById(jsonData.elementId);
            setElementInnerHtml(element, jsonData.html);
            return true;

        case operations.EXECUTE_JAVASCRIPT:
            //console.debug("EXECUTE_JAVASCRIPT operation received " + jsonData.javascript);
            executeJavascript(jsonData.javascript);
            return true;

    }
    return false;
}

function DocumentControl(name) {
    this.control_name = name
    this.message_func = function (operations,jsonData) {
        if(!processDocumentOperations(operations, jsonData)) {
            console.error("Invalid operation " + jsonData.op);
        }
    };
}
