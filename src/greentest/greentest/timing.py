# Copyright (c) 2018 gevent community
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

import time

import gevent

from greentest import sysinfo
from greentest import leakcheck
from greentest.testcase import TestCase


class _DelayWaitMixin(object):

    _default_wait_timeout = 0.01
    _default_delay_min_adj = 0.001
    if not sysinfo.RUNNING_ON_APPVEYOR:
        _default_delay_max_adj = 0.11
    else:
        # Timing resolution is extremely poor on Appveyor
        # and subject to jitter.
        _default_delay_max_adj = 1.5

    def wait(self, timeout):
        raise NotImplementedError('override me in subclass')

    def _check_delay_bounds(self, timeout, delay,
                            delay_min_adj=None,
                            delay_max_adj=None):
        delay_min_adj = self._default_delay_min_adj if not delay_min_adj else delay_min_adj
        delay_max_adj = self._default_delay_max_adj if not delay_max_adj else delay_max_adj
        self.assertTimeWithinRange(delay,
                                   timeout - delay_min_adj,
                                   timeout + delay_max_adj)

    def _wait_and_check(self, timeout=None):
        if timeout is None:
            timeout = self._default_wait_timeout

        # gevent.timer instances have a 'seconds' attribute,
        # otherwise it's the raw number
        seconds = getattr(timeout, 'seconds', timeout)

        start = time.time()
        try:
            result = self.wait(timeout)
        finally:
            self._check_delay_bounds(seconds, time.time() - start,
                                     self._default_delay_min_adj,
                                     self._default_delay_max_adj)
        return result

    def test_outer_timeout_is_not_lost(self):
        timeout = gevent.Timeout.start_new(0.001, ref=False)
        try:
            with self.assertRaises(gevent.Timeout) as exc:
                self.wait(timeout=1)
            self.assertIs(exc.exception, timeout)
        finally:
            timeout.close()


class AbstractGenericWaitTestCase(_DelayWaitMixin, TestCase):
    # pylint:disable=abstract-method

    _default_wait_timeout = 0.2
    _default_delay_min_adj = 0.1
    if not sysinfo.RUNNING_ON_APPVEYOR:
        _default_delay_max_adj = 0.11
    else:
        # Timing resolution is very poor on Appveyor
        # and subject to jitter
        _default_delay_max_adj = 1.5

    @leakcheck.ignores_leakcheck # waiting checks can be very sensitive to timing
    def test_returns_none_after_timeout(self):
        result = self._wait_and_check()
        # join and wait simply return after timeout expires
        self.assertIsNone(result)


class AbstractGenericGetTestCase(_DelayWaitMixin, TestCase):
    # pylint:disable=abstract-method

    Timeout = gevent.Timeout

    def cleanup(self):
        pass

    def test_raises_timeout_number(self):
        with self.assertRaises(self.Timeout):
            self._wait_and_check(timeout=0.01)
        # get raises Timeout after timeout expired
        self.cleanup()

    def test_raises_timeout_Timeout(self):
        timeout = gevent.Timeout(self._default_wait_timeout)
        try:
            self._wait_and_check(timeout=timeout)
        except gevent.Timeout as ex:
            self.assertIs(ex, timeout)
        finally:
            timeout.close()
        self.cleanup()

    def test_raises_timeout_Timeout_exc_customized(self):
        error = RuntimeError('expected error')
        timeout = gevent.Timeout(self._default_wait_timeout, exception=error)
        try:
            with self.assertRaises(RuntimeError) as exc:
                self._wait_and_check(timeout=timeout)

                self.assertIs(exc.exception, error)
                self.cleanup()
        finally:
            timeout.close()
