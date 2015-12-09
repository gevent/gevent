# Copyright (c) 2008 AG Projects
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

import sys
import greentest
import weakref
import time
import gc
from gevent import sleep, Timeout
DELAY = 0.04


class Error(Exception):
    pass


class Test(greentest.TestCase):

    @greentest.skipOnAppVeyor("Timing is flaky, especially under Py 3.4/64-bit")
    def test_api(self):
        # Nothing happens if with-block finishes before the timeout expires
        t = Timeout(DELAY * 2)
        assert not t.pending, repr(t)
        with t:
            assert t.pending, repr(t)
            sleep(DELAY)
        # check if timer was actually cancelled
        assert not t.pending, repr(t)
        sleep(DELAY * 2)

        # An exception will be raised if it's not
        try:
            with Timeout(DELAY) as t:
                sleep(DELAY * 10)
        except Timeout as ex:
            assert ex is t, (ex, t)
        else:
            raise AssertionError('must raise Timeout')

        # You can customize the exception raised:
        try:
            with Timeout(DELAY, IOError("Operation takes way too long")):
                sleep(DELAY * 10)
        except IOError as ex:
            assert str(ex) == "Operation takes way too long", repr(ex)

        # Providing classes instead of values should be possible too:
        try:
            with Timeout(DELAY, ValueError):
                sleep(DELAY * 10)
        except ValueError:
            pass

        try:
            1 / 0
        except:
            try:
                with Timeout(DELAY, sys.exc_info()[0]):
                    sleep(DELAY * 10)
                    raise AssertionError('should not get there')
                raise AssertionError('should not get there')
            except ZeroDivisionError:
                pass
        else:
            raise AssertionError('should not get there')

        # It's possible to cancel the timer inside the block:
        with Timeout(DELAY) as timer:
            timer.cancel()
            sleep(DELAY * 2)

        # To silent the exception before exiting the block, pass False as second parameter.
        XDELAY = 0.1
        start = time.time()
        with Timeout(XDELAY, False):
            sleep(XDELAY * 2)
        delta = (time.time() - start)
        self.assertTimeWithinRange(delta, 0, XDELAY * 2)

        # passing None as seconds disables the timer
        with Timeout(None):
            sleep(DELAY)
        sleep(DELAY)

    def test_ref(self):
        err = Error()
        err_ref = weakref.ref(err)
        with Timeout(DELAY * 2, err):
            sleep(DELAY)
        del err
        gc.collect()
        assert not err_ref(), repr(err_ref())

    def test_nested_timeout(self):
        with Timeout(DELAY, False):
            with Timeout(DELAY * 10, False):
                sleep(DELAY * 3 * 20)
            raise AssertionError('should not get there')

        with Timeout(DELAY) as t1:
            with Timeout(DELAY * 20) as t2:
                try:
                    sleep(DELAY * 30)
                except Timeout as ex:
                    assert ex is t1, (ex, t1)
                assert not t1.pending, t1
                assert t2.pending, t2
            assert not t2.pending, t2

        with Timeout(DELAY * 20) as t1:
            with Timeout(DELAY) as t2:
                try:
                    sleep(DELAY * 30)
                except Timeout as ex:
                    assert ex is t2, (ex, t2)
                assert t1.pending, t1
                assert not t2.pending, t2
        assert not t1.pending, t1


if __name__ == '__main__':
    greentest.main()
