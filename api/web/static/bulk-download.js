var ws = null;
var socketId = null;
var instanceId = null;

function isActiveDuringClickCallback(obj) {
    // This is flipped because active class is added after click callback.
    // Since there are only two states (active or inactive) we can be sure
    // that if it is active it will be inactive after this call.
    var wasActiveBeforeClick = obj.hasClass('active');
    return !wasActiveBeforeClick;
}


var selectDataArea;
var progressArea;
var bytesSlider;
var bytesSliderDescription;
var startDownloadButton;
var continueDownloadButton;
var progressBarContainers;

var bulkDownloadStartEpochMs = null;
var bulkDownloadEndEpochMs = null;

var cacheTimeSlider;

function setupBulkDownload(socketOptions, bulkDownloadLink, providerId, placeId, epochMinMs, epochMaxMs) {
    providerId = undefArg(providerId);
    placeId = undefArg(placeId);
    epochMinMs = undefArg(epochMinMs);
    epochMaxMs = undefArg(epochMaxMs);

    selectDataArea = $('#collapseOne');
    progressArea = $('#collapseTwo');
    bytesSlider = $('#num-bytes-per-batch-slider');
    bytesSliderDescription = $('#num-bytes-per-batch-slider-description');
    startDownloadButton = $('#start-download-button');
    continueDownloadButton = $('#continue-button');
    progressBarContainers = $("#progress-bar-total-container,#progress-bar-current-batch-container");
    cacheTimeSlider = $('#cache-time-slider');

    var continueDownloadButtonDownloadCompleteText = '<i class="icon-chevron-right"></i>Download Complete';
    var continueDownloadButtonNormalText = '<i class="icon-chevron-right"></i>Continue Download';
    continueDownloadButton.html(continueDownloadButtonNormalText);

    selectDataArea.collapse({toggle : false, parent:'#accordion2'});
    progressArea.collapse({toggle : false, parent:'#accordion2'});

    $('.data-req-cb').each(function() {
        var thisId = $(this).attr('id');
        var isRadio = $(this).parent().hasClass('custom-buttons-radio');

        var buttonCb = function(obj, isActive) {
            var theId = $(obj).attr('id');

            var isActiveCookie;
            if(isActive) {
                isActiveCookie = '1';
            } else {
                isActiveCookie = '0';
            }

            $.cookie(theId, isActiveCookie, {expires: 7});
        };

        setupSpecialButtons($(this), buttonCb);

        var isChecked = $.cookie(thisId);
        var _isChecked = undefArg(isChecked);

        isChecked = isChecked == '1';

        if(_isChecked != null) {
            if(!isChecked) {
                $(this).removeClass('active');
            } else {
                $(this).addClass('active');
            }
        }
    });

    var initialBatchSizeBytes = 1024 * 1024 * 8;
    var batchSizeBytes = initialBatchSizeBytes;

    bytesSlider.slider({
        range: false,
        min: 1024 * 1024,
        max: 1024 * 1024 * 256,
        values: [ initialBatchSizeBytes ],
        slide: function( event, ui ) {
            batchSizeBytes = ui.values[0];
            updateBatchSizeDescription();
        }
    });
    var updateBatchSizeDescription = function() {
        bytesSliderDescription.html('<p>' + bytesToSize(batchSizeBytes) + '</p>')
    };
    updateBatchSizeDescription();

    if(epochMinMs != null && epochMaxMs != null) {
        var updateTimeSliderDescription = function(uiMin, uiMax) {
            var minDate = getNiceDateStringFromEpoch(uiMin);
            var maxDate = getNiceDateStringFromEpoch(uiMax);
            $("#cache-time-slider-description-min").html( "<p><b>" + minDate + "</b></p>");
            $("#cache-time-slider-description-max").html( "<p><b>" + maxDate + "</b></p>");
            setBulkDownloadEpochMs(uiMin, uiMax);
        };

        cacheTimeSlider.slider({
            range: true,
            min: epochMinMs,
            max: epochMaxMs,
            values: [ epochMinMs, epochMaxMs ],
            slide: function( event, ui ) {
                updateTimeSliderDescription(ui.values[0], ui.values[1]);
            }
        });
        updateTimeSliderDescription(epochMinMs, epochMaxMs);
    }

    var onSocketClosed = function(graceful, reason) {
        continueDownloadButton.prop('disabled',true);
        startDownloadButton.attr('disabled',false);
        startDownloadButton.attr('current-state',0);
        startDownloadButton.text('Start Download');

        progressBarContainers.removeClass("active");

        $('.disable-while-downloading,.disable-while-downloading-not-active').each(function() {
            if(!undefArg(this.was_disabled_before)) {
                $(this).removeAttr('disabled','disabled');
            }
        });

        if(!graceful && $('#progress-bar-total').width() < 100) {
            console.error('Download interrupted');
        } else {
            if(graceful) {
                progressBarContainers.width('100%');
                continueDownloadButton.html(continueDownloadButtonDownloadCompleteText);
            }
        }
    };

    startDownloadButton.click(function(){
        var state = $(this).attr('current-state');
        if(state == 0) {
            $(this).attr('current-state',1);
            progressArea.collapse('show');
            $(this).text('Cancel Download');
            $('#progress-bar-total,#progress-bar-current-batch').width('0');
            progressBarContainers.addClass("active");
            continueDownloadButton.prop('disabled',true);
            continueDownloadButton.html(continueDownloadButtonNormalText);

            var nameDic = {};
            $('.data-req-cb').each(function() {
                var thisName = $(this).attr('name');
                nameDic[thisName] = $(this).hasClass('active');
            });

            $('.disable-while-downloading-not-active').each(function() {
                if(!$(this).hasClass('active')) {
                    this.was_disabled_before = $(this).attr('disabled');
                    $(this).attr('disabled','disabled');
                }
            });
            $('.disable-while-downloading').each(function() {
                this.was_disabled_before = $(this).attr('disabled');
                $(this).attr('disabled','disabled');
            });

            nameDic['batchSizeBytes'] = batchSizeBytes;

            if(providerId != null && placeId != null) {
                nameDic['provider_id'] = providerId;
                nameDic['place_id'] = placeId;
            }

            if(bulkDownloadStartEpochMs != null) {
                nameDic['start_epoch'] = bulkDownloadStartEpochMs;
            }
            if(bulkDownloadEndEpochMs != null) {
                nameDic['end_epoch'] = bulkDownloadEndEpochMs;
            }

            var wsUrl = buildUrl(bulkDownloadLink,nameDic);

            ws = new Socket(wsUrl, socketOptions, onSocketClosed);
            ws.add(new DocumentControl('BulkDownloadDataWsg'));
        } else {
            if(ws != null) {
                $(this).attr('current-state',2);
                $(this).text('Cancelling..');
                $(this).attr('disabled','disabled');
                ws.close();
            }
        }
    });
}

function openTunnel(base, id) {
    downloadUrl(base, id);
}

function openTunnels() {
    var prefix = '/instance/'+instanceId+'/bulk_download_provider/'+socketId+'/';
    if($('#c3').hasClass('active')) {
        openTunnel(prefix, 'tweet_tunnel');
    }
    openTunnel(prefix, 'user_tunnel');
}

function setSocketId(p_instanceId, p_socketId) {
    socketId = p_socketId;
    instanceId = p_instanceId;
    console.info('Socket ID set to ' + socketId);
    console.info('Instance ID set to ' + instanceId);

    openTunnels();
}

function continueDownload() {
    progressBarContainers.addClass("active");
    continueDownloadButton.prop('disabled',true);

    openTunnels();
}

function onBatchEnd() {
    progressBarContainers.removeClass("active");
    continueDownloadButton.prop('disabled',false);
}

function onFinished() {
    console.log('Completely finished download');
    ws.close();
}

function setBulkDownloadEpochMs(startEpochMs, endEpochMs) {
    bulkDownloadStartEpochMs = startEpochMs;
    bulkDownloadEndEpochMs = endEpochMs;
}