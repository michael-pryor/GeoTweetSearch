from pymongo.errors import DuplicateKeyError
from api.caching.caching_shared import getDatabase
from api.core.utility import getUniqueId

def getInstanceCodeCollection():
    db = getDatabase()
    return db.instance_codes

def addCode(code, maxInstances):
    code = unicode(code)
    collection = getInstanceCodeCollection()
    collection.insert({'_id' : code, 'consume_count' : 0, 'max_consume_count' : maxInstances})

def getCode(maxInstances):
    while True:
        try:
            code = unicode(getUniqueId())
            addCode(code,maxInstances)
            return code
        except DuplicateKeyError:
            pass

def removeCode(code):
    code = unicode(code)
    collection = getInstanceCodeCollection()
    collection.remove({'_id' : code})

def resetCodeConsumerCounts():
    collection = getInstanceCodeCollection()
    return collection.update({},{'$set' : {'consume_count' : 0}}, multi = True)

def consumeCode(code):
    code = unicode(code)
    if code is None or len(code) < 1:
        return False

    collection = getInstanceCodeCollection()

    # Max consume count won't change during run time.
    # Records might be added/removed but the count won't change on an individual record.
    result = collection.find_one({'_id' : code})
    if result is None:
        return False

    maxConsumeCount = result['max_consume_count']

    result = collection.update( { '_id' : code, 'consume_count' : { '$lt' : maxConsumeCount } }, { '$inc' : { 'consume_count' : 1 } } )
    if result is None:
        return False

    return result['n'] > 0

def unconsumeCode(code):
    code = unicode(code)
    if code is None or len(code) < 1:
        return

    collection = getInstanceCodeCollection()
    collection.update( { '_id' : code, 'consume_count' : { '$gt' : 0 } }, { '$inc' : { 'consume_count' : -1 } } )


if __name__ == '__main__':
    resetCodeConsumerCounts()
    getInstanceCodeCollection().remove()
    theCode = getCode(1)
    print theCode
