var HELP_KEYWORDS = 1;
var HELP_GEOGRAPHICAL = 2;
var HELP_INFLUENCE = 3;

function InstanceHelp(accordionHelpKeywords, accordionHelpInfluence, accordionHelpGeographical) {
    var helpShowing = null;

    this.getHelpShowing = function() {
        return helpShowing;
    };

    this.showKeywordsHelp = function() {
        accordionHelpKeywords.show();
        accordionHelpInfluence.hide();
        accordionHelpGeographical.hide();
        helpShowing = HELP_KEYWORDS;
    };

    this.showGeographicalHelp = function() {
        accordionHelpKeywords.hide();
        accordionHelpInfluence.hide();
        accordionHelpGeographical.show();
        helpShowing = HELP_GEOGRAPHICAL;
    };

    this.showInfluenceHelp = function() {
        accordionHelpKeywords.hide();
        accordionHelpInfluence.show();
        accordionHelpGeographical.hide();
        helpShowing = HELP_INFLUENCE;
    };
}