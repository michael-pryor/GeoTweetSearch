import logging
import unittest
from pymongo import MongoClient
import pymongo
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import OperationFailure
from api.config import Configuration

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)
client = None
database = None

def _initializeUsePower2(collectionName):
    # I commented this out in case it was causing instability in MongoDB.
    pass
    #try:
    #    colModResult = getDatabase().command({'collMod' : collectionName , 'usePowerOf2Sizes' : True})
    #    logger.info('Set usePowerOf2Sizes flag for collection: %s, result: %s' % (collectionName, colModResult))
    #except OperationFailure as e:
    #    logger.warn('Failed to set usePowerOf2Sizes: %s' % e.message)

def getDatabase():
    global client
    global database

    if client is None:
        logger.info('Initializing mongo db connection: %s, %s' % (Configuration.MONGO_DB_IP, Configuration.MONGO_DB_PORT))

        # Disabling write concern might be a good idea, but could cause problems.. need to experiment.
        if Configuration.MONGO_WRITE_CONCERN_ENABLED:
            writeConcern = 1
        else:
            writeConcern = 0

        client = MongoClient(Configuration.MONGO_DB_IP, Configuration.MONGO_DB_PORT, w=writeConcern, socketTimeoutMS=Configuration.MONGO_OPERATION_TIMEOUT, connectTimeoutMS=Configuration.MONGO_CONNECTION_TIMEOUT, use_greenlets=True)

    if database is None:
        database = client.__getattr__(Configuration.MONGO_DB_DATABASE_NAME)

        if Configuration.MONGO_DB_DATABASE_AUTHENTICATION_ENABLED:
            username = Configuration.MONGO_DB_DATABASE_AUTHENTICATION_USER_NAME
            password = Configuration.MONGO_DB_DATABASE_AUTHENTICATION_PASSWORD
            database.authenticate(username, password)

        if Configuration.ENABLE_MONGO_PROFILING is True:
            database.set_profiling_level(pymongo.OFF)
            logger.info('Erasing old MongoDB profiling data..')
            getDatabase().system.profile.drop()

            logger.info('Enabling MongoDB profiling..')
            database.set_profiling_level(Configuration.MONGO_PROFILING_LEVEL)

    return database

def getCollection(collectionName):
    db = getDatabase()
    return getattr(db,collectionName)

def getCollections():
    return getDatabase().collection_names()

class testMongo(unittest.TestCase):
    def testDatabase(self):
        myData = {'_id' : '1', 'text' : 'hello world', 'myList' : [1,2,3,4]}

        db = getDatabase()
        assert(isinstance(db,Database))

        table = db.test_table
        assert(isinstance(table,Collection))

        if table.find_one({'_id' : '1'}) is not None:
            table.remove({'_id' : '1'})

        table.insert(myData)

        assert(table.find_one({'_id' : '1'}) is not None)

        table.remove({'_id' : '1'})

