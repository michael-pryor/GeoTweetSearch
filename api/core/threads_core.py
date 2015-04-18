import logging
import os
from threading import Thread
import traceback
import time
from api.config import Configuration
from api.core.utility import EventTimer

logger = logging.getLogger(__name__)

class BaseThread(Thread):
    def __init__(self, threadName, onTerminateFunc=None, criticalThread=None, maxFailures=None, failureBackoffMaximumMs=None):
        if criticalThread is None:
            criticalThread = True

        if  criticalThread:
            critString = '(critical)'
        else:
            critString = '(non critical)'

        name = '%s %s' % (threadName, critString)

        super(BaseThread,self).__init__(name=name)

        if failureBackoffMaximumMs is None:
            failureBackoffMaximumMs = Configuration.THREAD_FAILURE_DEFAULT_MAXIMUM_BACKOFF_MS

        if maxFailures is None:
            maxFailures = Configuration.THREAD_FAILURE_DEFAULT_MAXIMUM_COUNT


        self.stopped = False
        self.on_terminate_func = onTerminateFunc

        self.is_critical_thread = criticalThread
        self.failure_event_timer = EventTimer(maxFailures, failureBackoffMaximumMs * 2)
        self.on_failure_wait_before_restart_seconds = float(1)
        self.on_failure_wait_before_restart_seconds_maximum = float(failureBackoffMaximumMs) / 1000

    def _run(self):
        raise NotImplementedError

    def _onRestart(self, e):
        """ Called when thread fails and attempts to restart,
            run method will be called afterwards.
            @param e exception which triggered restart.
            @return True if """
        traceback.print_exc()

    def _onFailure(self, e):
        """ Called when restarts failed and thread is terminating. """
        traceback.print_exc()

    def run(self):
        needRestart = None
        while True:
            logger.info('Starting thread: %s' % self.getName())
            try:
                if needRestart:
                    self._onRestart(needRestart)
                    needRestart = None

                self._run()

                if not self.stopped:
                    raise Exception('Thread illegally exited')

                logger.warn('Thread legally exited and will be allowed to terminate: %s' % self.getName()) # looking at this, keep as warn for now.
                break # if we reach this point thread is terminating normally.
            except Exception as e:
                logger.error('Exception in thread: %s - %s (%s)' % (self.getName(), e.message, type(e)))

                if not self.failure_event_timer.onEvent():
                    if self.on_failure_wait_before_restart_seconds > 0:
                        if self.failure_event_timer.triggered_reset:
                            logger.error('Reset failure back off time to 1 second of thread: %s' % self.getName())
                            self.on_failure_wait_before_restart_seconds = float(1)

                        logger.error('Waiting %.2f seconds before restarting thread: %s' % (self.on_failure_wait_before_restart_seconds, self.getName()))
                        time.sleep(self.on_failure_wait_before_restart_seconds)

                        # Exponential increase in wait time (up to maximum).
                        if self.on_failure_wait_before_restart_seconds < self.on_failure_wait_before_restart_seconds_maximum:
                            self.on_failure_wait_before_restart_seconds *= 2

                            if self.on_failure_wait_before_restart_seconds > self.on_failure_wait_before_restart_seconds_maximum:
                                self.on_failure_wait_before_restart_seconds = self.on_failure_wait_before_restart_seconds_maximum

                    logger.error('Attempting to restart thread: %s' % self.getName())
                    needRestart = e
                    continue
                else:
                    try:
                        self._onFailure(e)
                    except Exception as e:
                        logger.error('Exception while terminating thread: %s, details: %s' % (self.getName(), e.message))

                    if self.is_critical_thread:
                        logger.error('Critical thread failed, terminating application - thread responsible: %s' % self.getName())
                        os._exit(0)
                    else:
                        logger.error('Thread failed without terminating application: %s' % self.getName())

                    break

        logger.warn('Thread terminating: %s' % self.getName()) # looking at this, keep as warn for now.
        if self.on_terminate_func:
            self.on_terminate_func()

    def stop(self):
        self.stopped = True