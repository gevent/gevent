from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from gevent import lock

import gevent.testing as greentest
from gevent.tests import test__semaphore


class TestLockMultiThread(test__semaphore.TestSemaphoreMultiThread):

    def _makeOne(self):
        return lock.RLock()

if __name__ == '__main__':
    greentest.main()
