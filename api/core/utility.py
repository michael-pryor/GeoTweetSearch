import hashlib
from math import sqrt, ceil, log
from collections import Hashable, OrderedDict, namedtuple, MutableMapping
import copy
import logging
import os
import string
import struct
from threading import  RLock, Lock
import unittest
import urllib
import uuid
import time
import sys

__author__ = 'Michael Pryor'

logger = logging.getLogger(__name__)

def getModulePath(pyName):
    return os.path.dirname(pyName)


def join(delim, theList):
    result = ""
    for item in theList:
        if item is not None:
            result += delim + ('%s' % item)
    return result[len(delim):]

def joinStringsToLengthPretty(strings, maxLength):
    result = ''

    count = 0
    for string in strings:
        remainingLength = maxLength - len(result)
        truncatedWord = string[:remainingLength]

        if len(truncatedWord) < len(string):
            if len(result) > 0:
                result = result[:-2]
            else:
                if remainingLength > 0:
                    result += truncatedWord
                    count += 1

            more = (len(strings) - count)
            if more > 0:
                result += '.. (%d more)' % more
            else:
                result += '..'

            return result
        else:
            if remainingLength > 0:
                result += truncatedWord + ', '
                count += 1

    return result[:-2]


def joinStringsGrammarPretty(strings):
    theList = list()

    for string in strings:
        if string is not None and len(string) > 0:
            theList.append(unicode(string))

    if len(theList) == 0:
        return ''

    if len(theList) == 1:
        return theList[0]

    if len(theList) > 1:
        result = ''
        listLength = len(theList)
        for n in range(0,listLength-1):
            result += theList[n] + ', '

        result = result[:-2]
        result += ' and ' + theList[listLength-1]
        return result

def getMidPoint(coord1, coord2):
    x1, y1 = coord1
    x2, y2 = coord2

    xMid = (x1 + x2) / 2
    yMid = (y1 + y2) / 2

    return xMid, yMid

def getMidPointBox(north1, north2, south1, south2):
    midNorth = getMidPoint(north1, north2)
    midSouth = getMidPoint(south1, south2)
    return getMidPoint(midNorth, midSouth)

def getDistance(coord1, coord2):
    x1, y1 = coord1
    x2, y2 = coord2
    return sqrt( (x2 - x1)**2 + (y2 - y1)**2 )

def joinLists(list1, list2):
    if list1 is None and list2 is None:
        return None

    if list1 is None:
        list1 = []

    if list2 is None:
        list2 = []

    return list1 + list2

def joinListOfLists(listOfLists):
    result = list()
    for subList in listOfLists:
        result += subList

    return result

def prepareLowerAlpha(text):
    """ Normalizes string removing spaces and making it lower case """
    if text is None:
        return None

    text = unicode(text).lower()
    result = ''
    lastWasSpace = False
    for x in text:
        if x in string.ascii_lowercase:
            result += x
            if lastWasSpace:
                lastWasSpace = False
        else:
            if not lastWasSpace and x == ' ':
                result += ' '
                lastWasSpace = True

    if lastWasSpace:
        result = result[:-1]

    return result

def extractWords(text):
    return text.split()



def urlEncodeText(text):
    if text is None:
        return None

    return urllib.quote(text)


def criticalSection(lock,function):
    lock.acquire()
    try:
        return function()
    finally:
        lock.release()

class AtomicReference(object):
    """ We use this object to make it clear that the reference is treated as atomic.
        Also, should reference changes no longer be atomic in a later version of Python,
        it will be easy to adapt the code as we only have to make changes to this class.

        More importantly we can do 'get and set' atomically, which would otherwise not
        be guarenteed by python interpreter. """

    def __init__(self, item):
        self._item = item
        self._lock = RLock()

    @property
    def item(self):
        self._lock.acquire()
        try:
            return self._item
        finally:
            self._lock.release()

    @item.setter
    def item(self, item):
        self._lock.acquire()
        try:
            self._item = item
        finally:
            self._lock.release()

    def getAndSet(self, item):
        self._lock.acquire()
        try:
            aux = self._item
            self._item = item
            return aux
        finally:
            self._lock.release()


""" A neat bit of lambda to reverse and return a list
    This works because None is evaluated to False. """
reverse_list = lambda x: x.reverse() or x
lower_item = lambda x: x.lower() or x

def getUniqueId():
    return uuid.uuid4()


class HashableImpl(Hashable):
    """ Basic hash layout for classes which have no convenient unique ID. """

    def __init__(self):
        self.id = hash(getUniqueId())

    def __hash__(self):
        return self.id

    def __str__(self):
        return str(self.id)

    def __eq__(self, other):
        return self.id == other.id

    def __ne__(self, other):
        return self.id != other.id


def getAddedItems(oldSet, newSet):
    return newSet.difference(oldSet)


def getRemovedItems(oldSet, newSet):
    return oldSet.difference(newSet)


def isDifference(oldSet, newSet):
    return len(oldSet.symmetric_difference(newSet)) > 0

def packArguments(*args, **kwargs):
    names = []
    finalArgs = dict()
    for i, arg in enumerate(args):
        name = 'arg%d' % i
        names.append(name)
        finalArgs[name] = arg

    for key, value in kwargs.iteritems():
        names.append(key)
        finalArgs[key] = value


    ntuple = namedtuple('packed_arguments',names)
    return ntuple(**finalArgs)

def callAllCombinations(list, maxSize, function):
    for i in range(0,len(list),1):
        for j in range(len(list),i,-1):
            if j-i > maxSize:
                continue

            thisQuery = list[i:j]
            function(thisQuery)

def getEpochMs():
    return time.time() * 1000

def convertEpochMsToGmTime(epochMs):
    epoch = epochMs / 1000
    return time.gmtime(epoch)

def convertGmTimeToString(g):
    assert isinstance(g, time.struct_time)
    return '%02d/%02d/%04d %02d:%02d:%02d' % (g.tm_mday, g.tm_mon, g.tm_year, g.tm_hour, g.tm_min, g.tm_sec)

def getDateTime():
    return convertGmTimeToString(convertEpochMsToGmTime(getEpochMs()))

def splitList(theList,maxSize):
    chunks = []
    counter = 0
    while True:
        chunk = theList[counter:counter+maxSize]
        if len(chunk) < 1:
            break
        chunks.append(chunk)
        counter += maxSize

    return chunks

def getPercentage(val, total):
    if total is None or total == 0:
        total = 1
        val = 0

    if val is None:
        val = 0

    if total < val:
        val = total

    return (float(val) / float(total)) * 100

class DummyIterable(object):
    def __init__(self):
        super(DummyIterable,self).__init__()

    def __iter__(self):
        while True:
            time.sleep(100)


def prune(function, items):
    """ Prunes any structure, including nested dicts/lists, removing timestamped
        items older than maxAge.

        @param function A function when given an item from the structure returns true if item should be removed,
                        false if not. If an exception is thrown from the function false is assumed.
        @param items structure of items. Iterable objects will be iterated through recursively.
        @return true if an item was removed. """
    # Single item
    try:
        iter(items)
    except TypeError:
        try:
            return function(items)
        except Exception:
            return False

    copyItems = copy.copy(items)

    # Dict iteration.
    itera = None
    try:
        itera = copyItems.iteritems()
    except TypeError:
        pass
    except AttributeError:
        pass

    if itera:
        for itemKey, itemValue in itera:
            if prune(function, itemValue):
                items.pop(itemKey)

        # Remove empty containers.
        if len(items) == 0:
            return True
        else:
            return False


    # List iteration.
    itera = None
    try:
        itera = iter(copyItems)
    except TypeError:
        pass

    if itera:
        for item in itera:
            if prune(function, item):
                items.remove(item)

        if len(items) == 0:
            return True
        else:
            return False


    return False


def doUrlEncode(string):
    return urllib.quote_plus(string.encode('utf-8'))

def hashStringToInteger32(string):
    hashFunc = hashlib.md5()
    hashFunc.update(doUrlEncode(string))
    trunc = hashFunc.digest()[:4]
    return struct.unpack("<L", trunc)[0]

class Timer(HashableImpl):
    def __init__(self, frequencyMs=None, tickOnFirstCall=True):
        super(Timer,self).__init__()

        if frequencyMs is None:
            frequencyMs = 0

        self.frequency = frequencyMs

        self._lock = RLock()
        self.tick_on_first_call = tickOnFirstCall
        self.has_ticked = False
        self.initialized_timer = getEpochMs()
        self.resetTimer()

    def resetTimer(self):
        with self._lock:
            self.timer = getEpochMs()

    @property
    def time_since_last_tick(self):
        with self._lock:
            return getEpochMs() - self.timer

    def tick_missed(self):
        with self._lock:
            count = 0

            # round down.
            timeSinceLastTick = self.time_since_last_tick
            count += int(timeSinceLastTick / self.frequency)

            oldTimer = self.timer
            if count > 0:
                self.timer += timeSinceLastTick

            if self.ticked():
                count += 1

            return count

    @property
    def time_since_constructed(self):
        with self._lock:
            return getEpochMs() - self.initialized_timer

    def ticked(self):
        with self._lock:
            newTimer = getEpochMs()

            if not self.has_ticked and self.tick_on_first_call:
                self.has_ticked = True
                ticked = True
            else:
                ticked = newTimer - self.timer > self.frequency

            if ticked:
                self.timer = newTimer

            return ticked

    def waitForTick(self):
        with self._lock:
            if not self.has_ticked and self.tick_on_first_call:
                timeToWaitSeconds = 0
                self.has_ticked = True
            else:
                timeToWaitMs = self.frequency - (getEpochMs() - self.timer)
                timeToWaitSeconds = timeToWaitMs / 1000

        if timeToWaitSeconds > 0:
            time.sleep(timeToWaitSeconds)

        self.resetTimer()
        return True

    @classmethod
    def rate_limited(cls, numTicks, timePeriod, tickOnFirstCall=True):
        frequency = timePeriod / numTicks
        logger.debug('Rate limited timer created, num ticks: %d, time period: %d, frequency %d' % (numTicks, timePeriod, frequency))
        return cls(frequency,tickOnFirstCall)


class EventTimer(Timer):
    def __init__(self, maxEventCount, withinTimeMs):
        super(EventTimer,self).__init__(withinTimeMs,False)
        self.max_event_count = maxEventCount
        self.time_frame = withinTimeMs

        self.event_count = 0
        self.triggered_reset = False

    def onEvent(self):
        """ @return True if max_event_count number of events
            happen within withinTimeMs of each other, where the
            gap since each previous event is < withinTimeMs. """

        if self.ticked():
            self.event_count = 0
            self.triggered_reset = True
        else:
            self.triggered_reset = False

        self.event_count += 1
        self.resetTimer()

        return self.event_count > self.max_event_count

    def resetEventCount(self):
        self.event_count = 0


class EventFrequencyCounter(object):
    # avoids us accidently creating a memory leak.
    MAX_MULTIPLIER = 200

    def __init__(self, updateFrequency, timePeriod):
        super(EventFrequencyCounter, self).__init__()

        self.timer = Timer(updateFrequency, False)
        self.count = 0

        self._last_count_cache = list()

        self.time_period = timePeriod
        self.multiplier = float(timePeriod) / float(updateFrequency)

        if self.multiplier > EventFrequencyCounter.MAX_MULTIPLIER:
            logger.error('Number of updates per time period is too high, either increase the limit or change parameters')
            assert False

        self.new_data = False

        self._lock = RLock()

    def _checkForTick(self):
        ticks = self.timer.tick_missed()
        with self._lock:
            while ticks > 1:
                ticks -= 1

                self._last_count_cache.append(0)

                if len(self._last_count_cache) > self.multiplier:
                    self._last_count_cache.pop(0)


            if ticks > 0:
                self._last_count_cache.append(self.count)

                if len(self._last_count_cache) > self.multiplier:
                    self._last_count_cache.pop(0)

                self.count = 0
                self.new_data = True

    def onEvent(self):
        with self._lock:
            self.count += 1
            self._checkForTick()

    @property
    def time_period_count(self):
        with self._lock:
            self._checkForTick()
            requiredCacheSize = float(self.time_period) / float(self.timer.frequency)

            total = 0
            numCacheItems = 0
            for item in self._last_count_cache:
                total += item
                numCacheItems += 1
                if numCacheItems == requiredCacheSize:
                    break

            if numCacheItems > 0:
                missingMultiplier = float(requiredCacheSize) / float(numCacheItems)
                total *= missingMultiplier
            else:
                total = 0

            return total

    def time_period_count_updated(self, returnLast=False, includeUpdateFlag=False, castToInteger=False):
        with self._lock:
            if self.new_data:
                result = self.time_period_count
                self.last_time_period_count = result
                self.new_data = False

                if castToInteger:
                    result = int(result)

                updated = True
            else:
                if returnLast:
                    try:
                        if castToInteger:
                           result = int(self.last_time_period_count)
                        else:
                           result = self.last_time_period_count
                    except AttributeError:
                        result = None
                else:
                    result = None

                updated = False

            if includeUpdateFlag:
                return result, updated
            else:
                return result

def parseInteger(value, minimum=None, maximum=None, default=None):
    if len(value) == 0:
        return default
    else:
        val = int(value)
        if minimum is not None and val < minimum:
            val = minimum
        elif maximum is not None and val > maximum:
            val= maximum

        return val

def parseString(theString, acceptableStrings=None, ignoreCase=True, default = None):
    if not isinstance(theString, basestring):
        logger.warn('parseString received bad type of: %s' % type(theString))
        return None

    if theString is None or len(theString) == 0:
        return default

    if acceptableStrings is None or len(acceptableStrings) == 0:
        return theString

    if ignoreCase:
        theString = theString.lower()

    for sub in acceptableStrings:
        if ignoreCase:
            sub = sub.lower()

        if theString == sub:
            return theString

    return default

def parseBoolean(theString, default = None):
    val = parseString(theString,['true','false','1','0'], ignoreCase=True)
    if val is None:
        if default is not None:
            return default
        else:
            return None

    return val == 'true' or val == '1'

class OrderedDictEx(MutableMapping):
    def __init__(self, fifo=True, maxSize=None, readImpactsOrder=False):
        super(OrderedDictEx,self).__init__()

        self._dic = OrderedDict()
        self.fifo = fifo
        self.max_size = maxSize
        self.read_impacts_order = readImpactsOrder

        self._recursing = False

        self._lock = RLock()
        self.recurse_count = 0

    def __setitem__(self, key, value):
        with self._lock:
            # Store items in order that key was last added.
            # This will ensure update has same impact on position
            # as setting the item.
            skipSizeCheck = False # optimization
            if key in self._dic:
                del self._dic[key]
                skipSizeCheck = True
            self._dic[key] = value

            if self.max_size is not None and not skipSizeCheck:
                while len(self._dic) > self.max_size:
                    self.removeOrderedItem()

    def __str__(self):
        return str(self._dic)

    def __unicode__(self):
        return unicode(self._dic)

    def __repr__(self):
        return repr(self._dic)

    def __len__(self):
        return len(self._dic)

    def __getitem__(self, key):
        with self._lock:
            val = self._dic[key]

            if self.read_impacts_order:
                self.__setitem__(key, val)

            return val

    def __delitem__(self, key):
        del self._dic[key]

    def __iter__(self):
        return self._dic.__iter__()

    def removeOrderedItem(self):
        return self._dic.popitem(not self.fifo)

def upperPowerTwo(value):
    if value == 0:
        return 1

    return int(pow(2, ceil(log(value, 2))))

def searchDictionary(searchName, searchSourceDict, maxResults=None, caseInsensitive=None):
    results = list()

    if caseInsensitive is None:
        caseInsensitive = True

    if caseInsensitive:
        searchName = searchName.lower()

    if maxResults is not None and maxResults < 1:
        return results

    count = 0

    for key, value in searchSourceDict.iteritems():
        if caseInsensitive:
            key = key.lower()

        if searchName in key:
            results.append(value)
            count += 1

            if maxResults is not None and count >= maxResults:
                break

    return results

def redirectOutputToLogger():
    """ Python prints stack traces to console but not to logger, so we
        monkey patch stderr and force it to write to logger. """
    class writer(object):
        def __init__(self):
            self.data = list()

        def write(self, string):
            if string.endswith('\n'):
                self.data.append(string[:-1])
                self.flush()
            else:
                self.data.append(string)

        def close(self):
            self.flush()

        def flush(self):
            logger.error(''.join(self.data))
            self.data = list()

    sys.stderr = writer()




class testUtility(unittest.TestCase):
    def testJoin(self):
        result = join('_', ['hello'])
        logger.info(result)
        assert(len(result) == 5)

        result = join('_', ['hello', 'world'])
        logger.info(result)
        assert(len(result) == 11)

        result = join('_', ['hello', 'big', 'wide', 'world'])
        logger.info(result)
        assert(len(result) == 20)

    def testAtomicReference(self):
        ref = AtomicReference('hello')
        logger.info('Current item: %s' % ref.item)
        assert ref.item == 'hello'

        previous_item = ref.getAndSet('world')
        logger.info('Previous item: %s' % previous_item)
        logger.info('Current item: %s' % ref.item)
        assert previous_item == 'hello'
        assert ref.item == 'world'

        previous_item = ref.getAndSet('new york')
        logger.info('Previous item: %s' % previous_item)
        logger.info('Current item: %s' % ref.item)
        assert previous_item == 'world'
        assert ref.item == 'new york'

    def testGetUniqueId(self):
        uid = getUniqueId()
        logger.info(uid)
        logger.info(hash(uid))
        assert uid is not None

        uid2 = getUniqueId()
        logger.info(uid2)
        logger.info(hash(uid2))
        assert uid2 is not None

        assert uid != uid2
        assert hash(uid) != hash(uid2)

    def testSetComparison(self):
        l = ['hello', 'world', 'whats', 'up']

        oldSet = set(l)
        newSet = set(l)

        assert not isDifference(oldSet, newSet)

        addedItems = getAddedItems(oldSet, newSet)
        assert len(addedItems) == 0

        removedItems = getRemovedItems(oldSet, newSet)
        assert len(removedItems) == 0

        newSet.remove('up')
        addedItems = getAddedItems(oldSet, newSet)
        assert len(addedItems) == 0

        removedItems = getRemovedItems(oldSet, newSet)
        assert len(removedItems) == 1
        assert 'up' in removedItems

        assert isDifference(oldSet, newSet)

        oldSet.remove('world')
        addedItems = getAddedItems(oldSet, newSet)
        assert len(addedItems) == 1
        assert 'world' in addedItems

        removedItems = getRemovedItems(oldSet, newSet)
        assert len(removedItems) == 1
        assert 'up' in removedItems

        assert isDifference(oldSet, newSet)

    def testPrepareLowerAlpha(self):
        str = 'Hello'
        result = prepareLowerAlpha(str)
        assert result == 'hello'

        str = 'H e  l l o 1 2 3 '
        result = prepareLowerAlpha(str)
        assert result == 'h e l l o'

        str = 'London, UK'
        result = prepareLowerAlpha(str)
        assert result == 'london uk'

        result = extractWords(result)
        print result

    def testPackArguments(self):
        result = packArguments('hello',hi='yoyoo')[1]
        print result.hii
        assert False

    def testCallAllCombinations(self):
        query = 'I spend half my time in London and half my time in Tel Aviv, Israel'
        query = prepareLowerAlpha(query)
        queries = extractWords(query)

        def func(query):
            query = ' '.join(query)
            print query

        callAllCombinations(queries,4,func)

    def testSplitList(self):
        l = [1,2,3,4,5,6,7,8,9,10]

        l = splitList(l,3)

        assert len(l) == 4
        assert len(l[0]) == 3
        assert len(l[1]) == 3
        assert len(l[2]) == 3
        assert len(l[3]) == 1

    def testTimer(self):
        loopTimer = Timer(10000,False)

        timer = Timer(2000,True)

        while not loopTimer.ticked():
            if timer.waitForTick():
                print 'ticked'
            print 'waiting'

        loopTimer = Timer(5000,False)
        timer = Timer.rate_limited(18,30000,True)

        while not loopTimer.ticked():
            time.sleep(0.01)
            if timer.ticked():
                print 'ticked rate limited'

    def testDistance(self):
        p1 = 5,5
        p2 = 20,25
        result1 = getDistance(p1,p2)
        result2 = getDistance(p2,p1)

        assert result1 == 25.0
        assert result1 == result2

    def testOrderedDictEx(self):
        dic = OrderedDictEx(fifo = True, maxSize = 5)
        dic[1] = 1
        dic[2] = 2
        dic[3] = 300

        assert dic[1] == 1
        assert dic[2] == 2
        assert dic[3] == 300

        assert dic.removeOrderedItem() == (1,1)
        assert len(dic) == 2

        dic[3] = 300
        dic[4] = 4000
        dic[5] = 50

        dic[6] = 70
        dic[7] = 9000
        assert dic.get(1) is None
        assert dic.get(2) is None
        assert dic[3] == 300
        assert dic[4] == 4000
        assert dic[5] == 50
        assert dic[6] == 70
        assert dic[7] == 9000

        assert len(dic) == 5


if __name__ == '__main__':
    eventTimer = EventFrequencyCounter(50,100)

    runTimer = Timer(60000, False)

    triggerEventTimer = Timer(100,True)

    switchToOtherTimer = Timer(10000, False)

    otherTriggerEventTimer = Timer(200, False)

    useOtherTimer = False

    while not runTimer.ticked():
        if useOtherTimer is False:
            if triggerEventTimer.ticked():
                eventTimer.onEvent()

                r = eventTimer.time_period_count_updated
                if r is not None:
                    print 'Event timer result: %s' % r
        else:
            if otherTriggerEventTimer.ticked():
                eventTimer.onEvent()

                r = eventTimer.time_period_count_updated
                if r is not None:
                    print 'Event timer result: %s' % r

        if switchToOtherTimer.ticked():
            print 'Switching timer'
            useOtherTimer = not useOtherTimer

        time.sleep(0.01)

