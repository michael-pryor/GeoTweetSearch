<div class="accordion" id="accordionHelp">
    <div class="accordion-group">
        <div class="accordion-heading">
            <a class="accordion-toggle active" data-toggle="collapse" data-parent="#accordionHelp" href="#collapseInstanceHelpOne">
                Keywords Filter
            </a>
        </div>
        <div id="collapseInstanceHelpOne" class="accordion-body collapse">
            <div class="accordion-inner accordion-inner-instance-help scrollable">
                <div class='row-fluid'>
                    <div class='span12'>
                        <p>Twitter allows us to select keywords to filter by; we can also filter by #hashtags and @mentions.</p>
                        <p>For example; if filtering by the keywords "<b>apples, oranges, this big world</b>" then the following tweets could be received:</p>
                        <ul>
                            <li>The <b>apples</b> tasted good</li>
                            <li>The <b>apples</b> and <b>oranges</b> were out of <b>this big world</b></li>
                            <li>In <b>this</b> imaginary <b>world</b>, there are not enough <b>big</b> giants</li>
                            <li><b>#apples</b></li>
                            <li><b>@oranges</b></li>
                        </ul>
                        <p>But the following would not be received:</p>
                        <ul>
                            <li>The apple tasted good -- <b>Must match exactly 'apples'</b></li>
                            <li>Where in the world am I? -- <b>Must match all of 'this big world'</b></li>
                            <li>#newapples -- <b>#hashtags and @mentions must match keywords exactly</b></li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>


        <div class="accordion-heading" style="border-top: 1px solid #e5e5e5;">
            <a class="accordion-toggle" data-toggle="collapse" data-parent="#accordionHelp" href="#collapseInstanceHelpTwo">
                Geographical Location Filter
            </a>
        </div>
        <div id="collapseInstanceHelpTwo" class="accordion-body collapse">
            <div class="accordion-inner accordion-inner-instance-help scrollable">
                <div class='row-fluid'>
                    <div class='span12'>
                        <p>Twitter allows us to specify geographic areas in which to receive <b>geolocated tweets</b>.</p>
                        <p>Filtering by geographic location is disjoint from any keywords filter.
                            For example; if filtering by geographic location <b>United Kingdom</b> and filtering by keywords <b>car</b>, <b>plane</b> and <b>train</b> then the following tweets could be received:</p>
                        <ul>
                            <li>'My name is David and I like running in parks' - <b>from location UK</b></li>
                            <li>'Hello I am from England!!' - <b>from location UK</b></li>
                            <li>'I want to learn to drive a <b>car</b>' - from location New York</li>
                            <li>'The <b>plane</b> was very scary' - from location San Francisco</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <div class="accordion-heading" style="border-top: 1px solid #e5e5e5;">
            <a class="accordion-toggle" data-toggle="collapse" data-parent="#accordionHelp" href="#collapseInstanceHelpThree">
                Influence
            </a>
        </div>
        <div id="collapseInstanceHelpThree" class="accordion-body collapse">
            <div class="accordion-inner accordion-inner-instance-help scrollable">
                <div class='row-fluid'>
                    <div class="span12">
                        <p>Influence is defined as the percentage of a person or place's followers that are from a given area. We keep track of
                            influence over time which means you can use our service to visualise how influence of a place varies over time for your specific keywords and locations.</p>

                        <p>Here are some examples of what you can use our service to visualise:</p>
                        <ul>
                            <li>In what <b>cities</b> will tweets originating from <b>London</b> most likely be read in?</li>
                            <li>Which <b>countries</b> are most influenced by tweets with <b>hashtag '#helloworld'</b> originating from <b>New York City</b> and the <b>United Kingdom</b>?</li>
                            <li>How much influence do tweets originating from <b>Europe</b> have on <b>Africa</b>?</li>
                        </ul>

                        <p>It takes time to receive information about a user's followers and this cannot be done in bulk, so we process each user individually. This configuration panel allows you to
                            target the users that we generate influence data for.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>