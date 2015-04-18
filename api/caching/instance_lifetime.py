import logging
from pymongo.errors import DuplicateKeyError
from api.caching.caching_shared import getDatabase

logger = logging.getLogger(__name__)

def getInstanceLifetimeCollection():
    return getDatabase().instance_lifetime

def addInstance(instanceKey, oauthToken, oauthSecret, instanceGeographicalSetupString, keywords, instanceSetupCode, startTime):
    try:
        getInstanceLifetimeCollection().insert({'_id' : {'instance_key' : instanceKey},
                                                'oauth_token' : oauthToken,
                                                'oauth_secret' : oauthSecret,
                                                'instance_geographical_setup_string' : instanceGeographicalSetupString,
                                                'keywords' : keywords,
                                                'instance_setup_code' : instanceSetupCode,
                                                'start_time' : startTime,
                                                'temporal_last_time_id' : {}})
    except DuplicateKeyError:
        pass

def removeInstance(instanceKey):
    getInstanceLifetimeCollection().remove({'_id' : {'instance_key' : instanceKey}})

def setInstanceTemporalSourceLastTime(instanceKey, sourceProviderId, sourcePlaceId, lastTimeId):
    getInstanceLifetimeCollection().update({'_id' : {'instance_key' : instanceKey}}, {'$set' : {'temporal_last_time_id.%s.%s' % (sourceProviderId,sourcePlaceId) : lastTimeId}})

def getInstances(onInstanceDataFunc):
    cursor = getInstanceLifetimeCollection().find()
    for item in cursor:
        logger.info(unicode(item))
        instanceKey = item['_id']['instance_key']
        oauthToken = item['oauth_token']
        oauthSecret = item['oauth_secret']
        instanceGeographicalSetupString = unicode(item['instance_geographical_setup_string'])
        instanceSetupCode = item['instance_setup_code']
        keywords = item['keywords']
        startTime = item['start_time']
        temporalLastTimeId = item['temporal_last_time_id']

        onInstanceDataFunc(instanceKey, oauthToken, oauthSecret, instanceGeographicalSetupString, keywords, instanceSetupCode, startTime, temporalLastTimeId)

if __name__ == '__main__':
    setInstanceTemporalSourceLastTime('test2',1,200,3)