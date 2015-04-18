from Queue import Queue, Empty
from threading import RLock, Thread, Event
import time
import gevent
from api.core import utility

__author__ = 'Michael Pryor'

class QueueEx(Queue):
    """ Implements an iterator on top of the queue class """
    def __init__(self, continueRunningCheck=None, checkFrequency=None):
        Queue.__init__(self)

        if continueRunningCheck is None:
            continueRunningCheck = lambda: True

        self.continue_running_check = continueRunningCheck
        self.check_frequency = checkFrequency

    def __iter__(self):
        while True:
            try:
                yield self.get(True, self.check_frequency)
            except Empty:
                if not self.continue_running_check():
                    return

class QueueGreenlet(Queue):
    """ Implements an iterator on top of the queue class """
    def __init__(self, continueRunningCheck=None, checkFrequency=None):
        Queue.__init__(self)

        if continueRunningCheck is None:
            continueRunningCheck = lambda: True

        self.continue_running_check = continueRunningCheck
        self.check_frequency = checkFrequency

    def __iter__(self):
        while True:
            try:
                gevent.sleep()
                yield self.get(True, self.check_frequency)
            except Empty:
                if not self.continue_running_check():
                    return


class QueueNotify(object):
    def __init__(self, continueRunningCheck=None, checkFrequency=None, notifyPositionFunc=None):
        super(QueueNotify,self).__init__()

        if continueRunningCheck is None:
            continueRunningCheck = lambda: True

        self._input_queue = []
        self._process_queue = []
        self._queue_lock = RLock()
        self._queue_event = Event()
        self.continue_running_check_timer = utility.Timer(checkFrequency*1000,False)

        self.continue_running_check = continueRunningCheck
        self.notify_position_func = notifyPositionFunc
        self.check_frequency = checkFrequency
        self.last_processed_item = None

    def __iter__(self):
        while True:
            # Wait for signal from producer, or for timeout to expire.
            # If timeout expires isContinueRunningCheck will be true,
            # and we should check if we should break out of the loop.
            isContinueRunningCheck = not self._queue_event.wait(self.check_frequency)

            # Acquire the lock and copy the queue to process it.
            # Then clear the event while we have control of the lock.
            # This ensures that the copy of the queue we have is up to date
            # at the moment we clear the signal, so that items are not missed
            # if a producer tries to add while we make the copy or between making
            # the copy and clearing the event.
            #
            # It avoids the situation: p1 signals, thread copies, p2 signals, thread clears signal.
            # Here p2's items would be missed out. The setup we have makes sure p2 will wait before
            # adding items so it is: p1 signals, thread copies, thread clears signal, p2 signals.
            self._queue_lock.acquire()
            try:
                if not isContinueRunningCheck:
                    self._process_queue += list(self._input_queue)
                    self._input_queue = []
                    self._queue_event.clear()
            finally:
                self._queue_lock.release()

            # Check if we should continue running.
            if isContinueRunningCheck or self.continue_running_check_timer.ticked():
                if not self.continue_running_check():
                    return

            # Process copy of queue.
            if len(self._process_queue) > 0:
                resultItem = self._process_queue.pop(0)
                self.last_processed_item = resultItem

                # Do continue running checks while processing.
                if self.continue_running_check_timer.ticked():
                    if not self.continue_running_check():
                        return

                # Notify items in the queue of their position.
                # -1 position means just removed.
                if self.notify_position_func is not None:
                    self.notify_position_func(resultItem, -1, None)

                    count = 0
                    for item in self._process_queue:
                        self.notify_position_func(item, count, resultItem)
                        count += 1

                # Yield item.
                yield resultItem

    def qsize(self):
        self._queue_lock.acquire()
        try:
            return len(self._input_queue) + len(self._process_queue)
        finally:
            self._queue_lock.release()

    def put(self, item):
        # Put an item onto the queue and then signal.
        # Make sure we do this within lock, see documentation of __iter__.
        self._queue_lock.acquire()
        try:
            # self.qsize() is the position that the item will be added at.
            self.notify_position_func(item, self.qsize(), self.last_processed_item)
            self._input_queue.append(item)
            self._queue_event.set()
        finally:
            self._queue_lock.release()


class th(Thread):
    def __init__(self,queue):
        super(th,self).__init__()
        self.queue = queue

    def run(self):
        for item in self.queue:
            print 'Consumer received item from queue: %s, %d' % (item, self.queue.qsize())
            time.sleep(0.5)
        print 'done'


if __name__ == '__main__':
    def continueRunningCheck():
        print 'Consumer continue running check'
        return True

    def notifyPositionFunc(item, position, waitingFor):
        print 'Item %d is at position %d, waiting for: %s' % (item, position, waitingFor)

    q = QueueNotify(continueRunningCheck,100,notifyPositionFunc)
    t = th(q)
    t.start()

    count = 0

    while True:
        count += 1
        time.sleep(0.1)
        print 'Producer adding to queue'
        q.put(count)