function Socket(path, operations, onDisconnect) {
    var loc = window.location;
    var ws = new WebSocket(path);

    var closed = false;

    onDisconnect = undefArg(onDisconnect);

    ws.onopen = function() {
        console.info("Web socket connected to " + path + " successfully");
    };

    ws.onerror = function(evt) {
        console.error("Web socket error, code: " + evt.code);
    };

    ws.onclose = function(evt) {
        if(!closed) {
            console.error("Web socket disconnected from server, code: " + evt.code);
        } else {
            console.info("Web socket gracefully disconnected from server");
        }

        if(onDisconnect != null) {
            onDisconnect(closed,evt.code);
        }
    };

    this.controls = {};
    var controls = this.controls;

    this.operations = operations;

    this.close = function() {
        closed = true;
        ws.close();
    };

    this.add = function(control) {
        this.controls[control.control_name] = control.message_func;
    };

    this.removeByName = function(controlName) {
        if(controlName in this.controls) {
            delete this.controls[controlName];
            return true;
        } else {
            return false;
        }
    };

    this.remove = function(control) {
        return this.removeByName(control.control_name);
    };

    this.send = function(data) {
        ws.send(data);
    };

    ws.onmessage = function (evt) {
        var jsonData = $.parseJSON(evt.data);

        var key;
        for(key in jsonData) {
            if (!(key in controls)) {
                if('static_op' in jsonData) {
                    var static_op = jsonData['static_op'];
                    if(static_op == operations['PING']) {
                        //console.info('Received ping');
                        this.send("PING_BACK")
                    } else {
                        console.error('Received invalid static operation: ' + static_op);
                    }
                } else {
                    console.error('Message received for invalid control: ' + key);
                }
                continue;
            }

            // Call control's control function.
            controls[key](operations, jsonData[key]);
        }
    };
}