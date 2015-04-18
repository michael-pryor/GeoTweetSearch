function getPage(url, onSuccess, onFail, onAlways) {
    onFail = undefArg(onFail);
    onAlways = undefArg(onAlways);

    $.ajax(url, {type: 'GET',
                 dataType: 'json'})
              .error(function(obj, errorMessage, errorThrown) {
                        console.error('HTTP query to ' + url + ' failed with reason: ' + obj.status + ' (' + obj.statusText + ') - error message: ' + errorMessage + ', error thrown: ' + errorThrown);
                        if(onFail !== null) {
                            onFail();
                        }
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