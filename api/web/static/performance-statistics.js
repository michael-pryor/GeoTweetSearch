var onStatistics = function(stats) {
    var statisticsPerSecondDiv = $('.per-second-div').find('p');
    var statisticsPerMinuteDiv = $('.per-minute-div').find('p');
    var statisticsPerHourDiv = $('.per-hour-div').find('p');
    var statisticsPerDayDiv = $('.per-day-div').find('p');

    stats = $.parseJSON(stats);

    var successStats = stats[0];
    var tweetsPerSecond = successStats[0];
    var tweetsPerMinute = successStats[1];
    var tweetsPerHour = successStats[2];
    var tweetsPerDay = successStats[3];

    if(tweetsPerSecond != null) {
        var tps = tweetsPerSecond + ' TPS';
        statisticsPerSecondDiv.html(tps);
    }

    if(tweetsPerMinute != null) {
        var tpm = tweetsPerMinute + ' TPM';
        statisticsPerMinuteDiv.html(tpm);
    }

    if(tweetsPerHour != null) {
        var tph = tweetsPerHour + ' TPH';
        statisticsPerHourDiv.html(tph);
    }

    if(tweetsPerDay != null) {
        var tpd = tweetsPerDay + ' TPD';
        statisticsPerDayDiv.html(tpd);
    }

    var failStats = stats[1];
    var failTweetsPerSecond = failStats[0];
    var failTweetsPerMinute = failStats[1];
    var failTweetsPerHour = failStats[2];
    var failTweetsPerDay = failStats[3];

    if(failTweetsPerSecond != null) {
        console.info(failTweetsPerSecond + ' FTPS');
    }

    if(failTweetsPerMinute != null) {
        console.info(failTweetsPerMinute + ' FTPM');
    }

    if(failTweetsPerHour != null) {
        console.info(failTweetsPerHour + ' FTPH');
    }

    if(failTweetsPerDay != null) {
        console.info(failTweetsPerDay + ' FTPD');
    }
};