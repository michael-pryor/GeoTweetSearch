function getPage(url, onSuccess, onFail, onAlways) {
    onFail = undefArg(onFail);
    onAlways = undefArg(onAlways);

    function doCall() {
           $.ajax(url, {type: 'GET',
                        dataType: 'json',
                        //async: false,
                        timeout:10000,
                        retryLimit:10,
                        retryCount:0})
              .error(function(obj, errorMessage, errorThrown) {
                        console.error('HTTP query to ' + url + ' failed with reason: ' + obj.status + ' (' + obj.statusText + ') - error message: ' + errorMessage + ', error thrown: ' + errorThrown);
                        retryCount = this.retryCount
                        retryLimit = this.retryLimit
                        setTimeout ( function(){
                            retryCount++;
                            if (retryCount <= retryLimit) {
                                console.error('Retrying, count ' + retryCount + ' of ' + retryLimit);
                                doCall();
                            }
                         }, 500 );
                    })
              .always(function() {
                        if(onAlways !== null) {
                            onAlways();
                        }
                    }
              )
              .success(function(data, textStatus, jqXHR){
                    console.info('Successfully retrieved data from url: ' + url + ' (status: ' + textStatus + ')');

                    if (onSuccess !== null) {
                        onSuccess(data);
                    }
              })
    }
    setTimeout(doCall, 100);
}