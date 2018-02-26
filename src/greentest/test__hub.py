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


if __name__ == '__main__':
    greentest.main()
