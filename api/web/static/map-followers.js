var mapFollowersIconCreateFunction = function(cluster) {
    var percentageOfFollowers = 0;
    var markers = cluster.getAllChildMarkers();

    $(markers).each(function() {
        percentageOfFollowers += $(this).attr('properties')['percentage'];
    });

    var isSingleLocation = $(markers).length == 1;


    // Taken from marker cluster source and modified.
    var c = ' marker-cluster-follower-location-';

    var totalFollowersStr;
    if(!isSingleLocation) {
        c += 'group-';
    }

    if (percentageOfFollowers < 20) {
        c += 'small';
    } else if (percentageOfFollowers < 40) {
        c += 'medium';
    } else {
        c += 'large';
    }

    // 100.0% is too large, so we need to force it to 100% to stop
    // it overflowing and wrapping the text into two lines.
    if(percentageOfFollowers < 100.0) {
        percentageOfFollowers = (percentageOfFollowers).toFixed(1) + '%';
    } else {
        percentageOfFollowers = 100 + '%'
    }

    if(isSingleLocation) {
        totalFollowersStr = '<b>' + percentageOfFollowers + '</b>';
    } else {
        totalFollowersStr = percentageOfFollowers;
    }

    return new L.DivIcon({ html: '<div><span>' + totalFollowersStr + '</span></div>', className: 'marker-cluster-follower-location' + c, iconSize: new L.Point(43, 43) });
    // End of taken from marker cluster source and modified.
};