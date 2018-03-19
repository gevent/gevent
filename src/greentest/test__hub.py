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
import greentest.timing
import time
import re
import gevent
from gevent import socket
from gevent.hub import Waiter, get_hub
from gevent._compat import PYPY

DELAY = 0.1


class TestCloseSocketWhilePolling(greentest.TestCase):

    def test(self):
        with self.assertRaises(Exception):
            sock = socket.socket()
            self._close_on_teardown(sock)
            get_hub().loop.timer(0, sock.close)
            sock.connect(('python.org', 81))

        gevent.sleep(0)


class TestExceptionInMainloop(greentest.TestCase):

    def test_sleep(self):
        # even if there was an error in the mainloop, the hub should continue to work
        start = time.time()
        gevent.sleep(DELAY)
        delay = time.time() - start

        delay_range = DELAY * 0.9
        self.assertTimeWithinRange(delay, DELAY - delay_range, DELAY + delay_range)

        error = greentest.ExpectedException('TestExceptionInMainloop.test_sleep/fail')

        def fail():
            raise error

        with get_hub().loop.timer(0.001) as t:
            t.start(fail)

            self.expect_one_error()

            start = time.time()
            gevent.sleep(DELAY)
            delay = time.time() - start

            self.assert_error(value=error)
            self.assertTimeWithinRange(delay, DELAY - delay_range, DELAY + delay_range)



class TestSleep(greentest.timing.AbstractGenericWaitTestCase):

    def wait(self, timeout):
        gevent.sleep(timeout)

    def test_simple(self):
        gevent.sleep(0)


class TestWaiterGet(greentest.timing.AbstractGenericWaitTestCase):

    def setUp(self):
        super(TestWaiterGet, self).setUp()
        self.waiter = Waiter()

    def wait(self, timeout):
        with get_hub().loop.timer(timeout) as evt:
            evt.start(self.waiter.switch)
            return self.waiter.get()


class TestWaiter(greentest.TestCase):

    def test(self):
        waiter = Waiter()
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
        self.assertTrue(str(waiter).startswith('<Waiter greenlet=<Greenlet "Greenlet-'))

        g.kill()


class TestPeriodicMonitoringThread(greentest.TestCase):

    def setUp(self):
        super(TestPeriodicMonitoringThread, self).setUp()
        self.monitor_thread = gevent.config.monitor_thread
        gevent.config.monitor_thread = True
        self.monitor_fired = 0

    def tearDown(self):
        if not self.monitor_thread and get_hub().periodic_monitoring_thread:
            # If it was true, nothing to do. If it was false, tear things down.
            get_hub().periodic_monitoring_thread.kill()
            get_hub().periodic_monitoring_thread = None
        gevent.config.monitor_thread = self.monitor_thread

    def _monitor(self, _hub):
        self.monitor_fired += 1

    def test_config(self):
        self.assertEqual(0.1, gevent.config.max_blocking_time)

    @greentest.ignores_leakcheck
    def test_blocking(self):
        import io
        hub = get_hub()
        monitor = hub.start_periodic_monitoring_thread()
        self.assertIsNotNone(monitor)
        before_funs = monitor._additional_monitoring_functions

        monitor.add_monitoring_function(self._monitor, 0)
        self.assertIn((self._monitor, 0), monitor.monitoring_functions())

        # We must make sure we have switched greenlets at least once,
        # otherwise we can't detect a failure.
        gevent.sleep(0.01)
        stream = hub.exception_stream = io.BytesIO() if str is bytes else io.StringIO()
        assert hub.exception_stream is stream
        try:
            time.sleep(0.3) # Thrice the default; PyPy is very slow to format stacks
            # XXX: This is racy even on CPython
        finally:
            monitor._additional_monitoring_functions = before_funs
            assert hub.exception_stream is stream
            del hub.exception_stream

        if not PYPY:
            # PyPy may still be formatting the stacks in the other thread.
            self.assertGreaterEqual(self.monitor_fired, 1)
            data = stream.getvalue()
            self.assertIn('appears to be blocked', data)
            self.assertIn('PeriodicMonitoringThread', data)


if __name__ == '__main__':
    greentest.main()
