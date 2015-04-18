import logging
import unittest
from api.core.utility import getEpochMs, convertGmTimeToString, convertEpochMsToGmTime, prune

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

class Timestamped(object):
    """ Classes should override this if they have a need to keep track of the age of objects.
        On construction the age is set to 0, and increments over time. """

    def __init__(self, constructedAt=None):
        object.__init__(self)
        self.touch()

        if constructedAt is None:
            self.constructed_at = getEpochMs()
        else:
            self.constructed_at = constructedAt

    def touch(self):
        self.timestamp = getEpochMs()

    @property
    def construct_age(self):
        return getEpochMs() - self.constructed_at

    @property
    def age(self):
        """ @return the age of the item. """
        return getEpochMs() - self.timestamp

    @property
    def date_time(self):
        return convertGmTimeToString(convertEpochMsToGmTime(self.timestamp))

    @staticmethod
    def prune(dataStructure, maxAge):
        prune(lambda item: item.age > maxAge, dataStructure)


class testTimestamp(unittest.TestCase):
    def testPrune(self):
        class MyItem(Timestamped):
            def __init__(self, age=None):
                Timestamped.__init__(self)

                if age is not None:
                    self.timestamp = getEpochMs() - age

            def __str__(self):
                return 'Age: %sms' % str(self.age)

            def __repr__(self):
                return '<%s>' % str(self)

        li = [MyItem(0), MyItem(1000), MyItem(2000), MyItem(3000)]

        logger.info(li[3].date_time)

        logger.info(li)
        Timestamped.prune(1200, li)
        logger.info(li)

        for item in li:
            assert item.age < 1200