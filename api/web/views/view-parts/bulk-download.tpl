<div class="row-fluid">
    <div class="span12">
        <div class="accordion" id="accordion2">
            <div class="accordion-group">
                <div class="accordion-heading">
                    <a class="accordion-toggle" data-toggle="collapse" data-parent="#accordion2" href="#collapseOne">
                        Select Required Data
                    </a>
                </div>
                <div id="collapseOne" class="accordion-body collapse in">
                    <div class="accordion-inner accordion-inner-bulk-download" style='min-height: 350px;'>
                        <div class='row-fluid' style='padding-bottom: 45px;'>
                            <div class='span12'>
                                <h4>Download Type</h4>
                                <p>Select what data you wish to download:</p>
                                <ul>
                                    <li>Tweet information: This includes details of tweets and the users who created the tweets. Follower information and analysis is not included.</li>
                                    <li>Full follower information: This includes users which we have retrieved follower information for, their followers (including non geocoded followers) and analysis performed on the followers.</li>
                                    <li>Short follower information: This includes users which we have retrieved follower information for but not their followers. This option produces a significantly smaller download file.</li>
                                </ul>
                                <div class="btn-group custom-buttons-radio">
                                    <button type="button" class="btn btn-default data-req-cb disable-while-downloading active" id="c3" name="tweet_info">Tweet Information</button>
                                    <button type="button" class="btn btn-default data-req-cb disable-while-downloading-not-active" id="c1" name="follower_info_full">Full Follower Information</button>
                                    <button type="button" class="btn btn-default data-req-cb disable-while-downloading-not-active" id="c2" name="follower_info_short">Short Follower Information</button>
                                </div>
                            </div>
                        </div>
                        %if defined('include_time_period_bar') and include_time_period_bar is True:
                        <div class='row-fluid'>
                            <div class='span12'>
                                <div class='row-fluid'>
                                    <h4>Download Time Period</h4>
                                </div>

                                <div class="row-fluid">
                                    <div class="span8">
                                        <div class="row-fluid slider-description">
                                            <div id="cache-time-slider-description-min" class="span6 pull-left"></div>
                                            <div id="cache-time-slider-description-max" class="span6 pull-right" style='text-align: right;'></div>
                                        </div>
                                        <div class="row-fluid" style="height: 15px; padding-bottom: 40px;">
                                            <div id="cache-time-slider" class="disable-while-downloading"></div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        %end
                        <div class='row-fluid'>
                            <div class="span12">
                                <div class='row-fluid'>
                                    <div class='span12'>
                                        <h4>Batch Size</h4>
                                        <p>The download is split into batches to help mitigate long download times. After each batch the download will pause. </p>
                                    </div>
                                </div>

                                <div class="row-fluid">

                                    <div class="span8">
                                        <div id="num-bytes-per-batch-slider-description" class="slider-description"></div>
                                        <div id="num-bytes-per-batch-slider" style='margin-bottom: 20px;' class="disable-while-downloading"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="accordion-heading" style="border-top: 1px solid #e5e5e5;">
                    <a class="accordion-toggle" data-toggle="collapse" data-parent="#accordion2" href="#collapseTwo">
                        Download Progress
                    </a>
                </div>
                <div id="collapseTwo" class="accordion-body collapse">
                    <div class="accordion-inner accordion-inner-bulk-download" style='min-height: 350px;'>
                        <div class="span12" id="BulkDownloadDataWsg_contents">
                            <div class="row-fluid"  style='padding-top: 15px;'>
                                <div class="span12">
                                    <p class="text-info"><b>Total Download</b></p>
                                    <div class="progress progress-success progress-striped active" id="progress-bar-total-container"><div class="bar" id="progress-bar-total" style="width: 0"></div></div>
                                </div>
                            </div>
                            <div class="row-fluid">
                                <div class="span12">
                                    <p class="text-info"><b>Current Batch</b></p><div class="progress progress-warning progress-striped active" id="progress-bar-current-batch-container"><div class="bar" id="progress-bar-current-batch" style="width: 0"></div></div>
                                </div>
                            </div>
                            <div class="row-fluid">
                                <div class="span12">
                                    <button class="btn btn-primary" type="button" onclick="continueDownload(); return false;" id="continue-button" disabled><i class="icon-chevron-right"></i>Continue Download</button>
                                    <br><br>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="row-fluid">
                    <div class="accordion-inner span12">
                        <button type="button" class="btn btn-primary" id="start-download-button" current-state = 0>Start Download</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>