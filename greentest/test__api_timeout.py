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

from __future__ import with_statement
import sys
import greentest
import weakref
import time
from gevent import sleep, Timeout, TimeoutError
from gevent.greenlet import _SilentException
DELAY = 0.04

class Error(Exception):
    pass

class Test(greentest.TestCase):

    def test_api(self):
        # Nothing happens if with-block finishes before the timeout expires
        with Timeout(DELAY*2):
            sleep(DELAY)
        sleep(DELAY*2) # check if timer was actually cancelled

        # An exception will be raised if it's not
        try:
            with Timeout(DELAY):
                sleep(DELAY*2)
        except TimeoutError:
            pass
        else:
            raise AssertionError('must raise TimeoutError')

        # You can customize the exception raised:
        try:
            with Timeout(DELAY, IOError("Operation takes way too long")):
                sleep(DELAY*2)
        except IOError, ex:
            assert str(ex)=="Operation takes way too long", repr(ex)

        # Providing classes instead of values should be possible too:
        try:
            with Timeout(DELAY, ValueError):
                sleep(DELAY*2)
        except ValueError:
            pass

        try:
            1/0
        except:
            try:
                with Timeout(DELAY, sys.exc_info()[0]):
                    sleep(DELAY*2)
                    raise AssertionError('should not get there')
                raise AssertionError('should not get there')
            except ZeroDivisionError:
                pass
        else:
            raise AssertionError('should not get there')

        # It's possible to cancel the timer inside the block:
        with Timeout(DELAY) as timer:
            timer.cancel()
            sleep(DELAY*2)

        # To silent the exception, pass None as second parameter. The with-block
        # will be interrupted with _SilentException, but it won't be propagated
        # outside.
        XDELAY=0.1
        start = time.time()
        with Timeout(XDELAY, None):
            sleep(XDELAY*2)
        delta = (time.time()-start)
        assert delta<XDELAY*2, delta

        # passing None as seconds disables the timer
        with Timeout(None):
            sleep(DELAY)
        sleep(DELAY)

    def test_ref(self):
        err = Error()
        err_ref = weakref.ref(err)
        with Timeout(DELAY*2, err):
            sleep(DELAY)
        del err
        assert not err_ref(), repr(err_ref())

    def test_nested_timeout(self):
        with Timeout(DELAY, None):
            with Timeout(DELAY*2, None):
                sleep(DELAY*3)
            raise AssertionError('should not get there')

        with Timeout(DELAY, _SilentException()):
            with Timeout(DELAY*2, _SilentException()):
                sleep(DELAY*3)
            raise AssertionError('should not get there')


        # this case fails and there's no intent to fix it.
        # just don't do it like that
        #with Timeout(DELAY, _SilentException):
        #    with Timeout(DELAY*2, _SilentException):
        #        sleep(DELAY*3)
        #    assert False, 'should not get there'


if __name__=='__main__':
    greentest.main()

