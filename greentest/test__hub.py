# Copyright (c) 2009 AG Projects
# Author: Denis Bilenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import greentest
import unittest
import time
import gevent
from gevent import core
from gevent import socket
import signal

DELAY = 0.1


class TestScheduleCall(greentest.TestCase):

#     def test_local(self):
#         lst = [1]
#         spawn(get_hub().schedule_call_local, DELAY, lst.pop)
#         sleep(DELAY*2)
#         assert lst == [1], lst

    def test_global(self):
        lst = [1]
        gevent.spawn(core.timer, DELAY, lst.pop)
        gevent.sleep(DELAY*2)
        assert lst == [], lst


class TestCloseSocketWhilePolling(greentest.TestCase):

    def test(self):
        try:
            sock = socket.socket()
            core.timer(0, sock.close)
            sock.connect(('python.org', 81))
        except Exception:
            gevent.sleep(0)
        else:
            assert False, 'expected an error here'


class TestExceptionInMainloop(greentest.TestCase):

    def test_sleep(self):
        # even if there was an error in the mainloop, the hub should continue to work
        start = time.time()
        gevent.sleep(DELAY)
        delay = time.time() - start

        assert delay >= DELAY*0.9, 'sleep returned after %s seconds (was scheduled for %s)' % (delay, DELAY)

        def fail():
            1/0

        core.timer(0, fail)

        start = time.time()
        gevent.sleep(DELAY)
        delay = time.time() - start

        assert delay >= DELAY*0.9, 'sleep returned after %s seconds (was scheduled for %s)' % (delay, DELAY)


class TestShutdown(unittest.TestCase):

    def _shutdown(self, seconds=0, fuzzy=0.01):
        start = time.time()
        gevent.hub.shutdown()
        delta = time.time() - start
        assert seconds - fuzzy < delta < seconds + fuzzy, (seconds-fuzzy, delta, seconds+fuzzy)

    def assert_hub(self):
        assert 'hub' in gevent.hub._threadlocal.__dict__

    def assert_no_hub(self):
        assert 'hub' not in gevent.hub._threadlocal.__dict__

    def test(self):
        assert not gevent.hub.get_hub().dead
        self._shutdown()
        self.assert_no_hub()

        # shutting down dead hub is silent
        self._shutdown()
        self._shutdown()
        self.assert_no_hub()

        # ressurect
        gevent.sleep(0)
        self.assert_hub()

        gevent.core.timer(0.1, lambda : None)
        self.assert_hub()
        self._shutdown(seconds=0.1)
        self.assert_no_hub()
        self._shutdown(seconds=0)
        self.assert_no_hub()


class TestSleep(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        gevent.sleep(timeout)


class Expected(Exception):
    pass


class TestSignal(greentest.TestCase):

    __timeout__ = 2

    def test_exception_goes_to_MAIN(self):
        def handler():
            raise Expected('TestSignal')
        gevent.signal(signal.SIGALRM, handler)
        signal.alarm(1)
        try:
            gevent.sleep(1.1)
            raise AssertionError('must raise Expected')
        except Expected, ex:
            assert str(ex) == 'TestSignal', ex


if __name__=='__main__':
    greentest.main()

