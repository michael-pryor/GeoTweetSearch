function queryGeocodeSearch(placeName, onSuccess, onFail, onAlways) {
    placeName = undefArg(placeName);
    if(placeName == null) {
        return null;
    }

    var urlArgs =  {'place_name' : placeName};
    var urlToLoadFrom = buildUrl('/geocode_search',urlArgs);
    console.info('Querying URL: ' + urlToLoadFrom);
    getPage(urlToLoadFrom, onSuccess, onFail, onAlways);
}