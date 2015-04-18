from api.twitter.flow.analysis_core import Analysis

__author__ = 'Michael Pryor'

class AnalysisLocations(Analysis):
    def __init__(self, userByLocation, tweetByLocation):
        Analysis.__init__(self, "AnalysisLocations", dataSignalers=[userByLocation,tweetByLocation])

    def processDataChange(self, signaler, data):
        if 'users_by_location' in data or 'tweets_by_location' in data:
            return data