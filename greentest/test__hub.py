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
import re
import sys
import gevent
from gevent import core
from gevent import socket
from gevent.hub import Waiter
import signal

DELAY = 0.1


class TestScheduleCall(greentest.TestCase):

    def test_global(self):
        lst = [1]
        gevent.spawn(core.timer, DELAY, lst.pop)
        gevent.sleep(DELAY * 2)
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

        assert delay >= DELAY * 0.9, 'sleep returned after %s seconds (was scheduled for %s)' % (delay, DELAY)

        def fail():
            raise greentest.ExpectedException('TestExceptionInMainloop.test_sleep/fail')

        core.timer(0, fail)

        start = time.time()
        gevent.sleep(DELAY)
        delay = time.time() - start

        assert delay >= DELAY * 0.9, 'sleep returned after %s seconds (was scheduled for %s)' % (delay, DELAY)


class TestShutdown(unittest.TestCase):

    def _shutdown(self, seconds=0, fuzzy=None):
        if fuzzy is None:
            fuzzy = max(0.05, seconds / 2.)
        start = time.time()
        gevent.hub.shutdown()
        delta = time.time() - start
        assert seconds - fuzzy < delta < seconds + fuzzy, (seconds - fuzzy, delta, seconds + fuzzy)

    def assert_hub(self):
        assert 'hub' in gevent.hub._threadlocal.__dict__

    def assert_no_hub(self):
        assert 'hub' not in gevent.hub._threadlocal.__dict__, gevent.hub._threadlocal.__dict__

    def test(self):
        # make sure Hub is started. For the test case when hub is not started, see test_hub_shutdown.py
        gevent.sleep(0)
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

        gevent.core.timer(0.1, lambda: None)
        self.assert_hub()
        self._shutdown(seconds=0.1)
        self.assert_no_hub()
        self._shutdown(seconds=0)
        self.assert_no_hub()


class TestSleep(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        gevent.sleep(timeout)

    def test_negative(self):
        self.switch_expected = False
        self.assertRaises(IOError, gevent.sleep, -1)
        if sys.platform != 'win32':
            from time import sleep as real_sleep
            try:
                real_sleep(-0.1)
            except IOError, real_ex:
                pass
        else:
            # XXX real_sleep(-0.1) hangs on win32
            real_ex = "[Errno 22] Invalid argument"
        try:
            gevent.sleep(-0.1)
        except IOError, gevent_ex:
            pass
        self.assertEqual(str(gevent_ex), str(real_ex))


class Expected(Exception):
    pass


if hasattr(signal, 'SIGALRM'):

    class TestSignal(greentest.TestCase):

        __timeout__ = 2

        def test_exception_goes_to_MAIN(self):
            def handler():
                raise Expected('TestSignal')
            gevent.signal(signal.SIGALRM, handler)
            signal.alarm(1)
            try:
                gevent.spawn(gevent.sleep, 2).join()
                raise AssertionError('must raise Expected')
            except Expected, ex:
                assert str(ex) == 'TestSignal', ex


class TestWaiter(greentest.GenericWaitTestCase):

    def setUp(self):
        super(TestWaiter, self).setUp()
        self.waiter = Waiter()

    def wait(self, timeout):
        evt = core.timer(timeout, self.waiter.switch, None)
        try:
            return self.waiter.get()
        finally:
            evt.cancel()

    def test(self):
        waiter = self.waiter
        self.assertEqual(str(waiter), '<Waiter greenlet=None>')
        waiter.switch(25)
        self.assertEqual(str(waiter), '<Waiter greenlet=None value=25>')
        self.assertEqual(waiter.get(), 25)

        waiter = Waiter()
        waiter.throw(ZeroDivisionError)
        assert re.match('^<Waiter greenlet=None exc_info=.*ZeroDivisionError.*$', str(waiter)), str(waiter)
        self.assertRaises(ZeroDivisionError, waiter.get)

        waiter = Waiter()
        g = gevent.spawn(waiter.get)
        gevent.sleep(0)
        assert str(waiter).startswith('<Waiter greenlet=<Greenlet at '), str(waiter)
        g.kill()


if __name__ == '__main__':
    greentest.main()
