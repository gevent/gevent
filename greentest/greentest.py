# Copyright (c) 2008-2009 AG Projects
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

# package is named greentest, not test, so it won't be confused with test in stdlib
import sys
import os
import errno
import unittest
import time

import gevent

disabled_marker = '-*-*-*-*-*- disabled -*-*-*-*-*-'
def exit_disabled():
    sys.exit(disabled_marker)

def exit_unless_25():
    if sys.version_info[:2]<(2, 5):
        exit_disabled()

class TestCase(unittest.TestCase):

    __timeout__ = 1
    switch_expected = True
    _switch_count = None

    def setUp(self):
        gevent.sleep(0) # switch at least once to setup signal handlers
        if hasattr(gevent.core, '_event_count'):
            self._event_count = (gevent.core._event_count(), gevent.core._event_count_active())
        hub = gevent.hub.get_hub()
        if hasattr(hub, 'switch_count'):
            self._switch_count = hub.switch_count
        self._timer = gevent.Timeout.start_new(self.__timeout__, RuntimeError('test is taking too long'))

    def tearDown(self):
        if hasattr(self, '_timer'):
            self._timer.cancel()
            hub = gevent.hub.get_hub()
            if self._switch_count is not None and hasattr(hub, 'switch_count'):
                name = getattr(self, '_testMethodName', '') # 2.4 does not have it
                if hub.switch_count < self._switch_count:
                    sys.stderr.write('WARNING: hub.switch_count decreased?\n')
                if hub.switch_count == self._switch_count and self.switch_expected:
                    sys.stderr.write('WARNING: %s.%s did not switch\n' % (type(self).__name__, name))
                if hub.switch_count > self._switch_count and not self.switch_expected:
                    sys.stderr.write('WARNING: %s.%s switched but expected not to\n' % (type(self).__name__, name))

            if hasattr(gevent.core, '_event_count'):
                event_count = (gevent.core._event_count(), gevent.core._event_count_active())
                if event_count > self._event_count:
                    args = (type(self).__name__, self._testMethodName, self._event_count, event_count)
                    sys.stderr.write('WARNING: %s.%s event count was %s, now %s\n' % args)
                    gevent.sleep(0.1)
        else:
            sys.stderr.write('WARNING: %s.setUp does not call base class setUp\n' % (type(self).__name__, ))


def find_command(command):
    for dir in os.getenv('PATH', '/usr/bin:/usr/sbin').split(os.pathsep):
        p = os.path.join(dir, command)
        if os.access(p, os.X_OK):
            return p
    raise IOError(errno.ENOENT, 'Command not found: %r' % command)

main = unittest.main

_original_Hub = gevent.hub.Hub

class CountingHub(_original_Hub):

    switch_count = 0

    def switch(self):
        self.switch_count += 1
        return _original_Hub.switch(self)

gevent.hub.Hub = CountingHub


def test_outer_timeout_is_not_lost(self):
    t = gevent.Timeout.start_new(0.01)
    try:
        self.wait(timeout=0.02)
    except gevent.Timeout, ex:
        assert ex is t, (ex, t)
    else:
        raise AssertionError('must raise Timeout')
    gevent.sleep(0.02)


class GenericWaitTestCase(TestCase):

    def wait(self, timeout):
        raise NotImplementedError('override me in subclass')

    test_outer_timeout_is_not_lost = test_outer_timeout_is_not_lost

    def test_returns_none_after_timeout(self):
        start = time.time()
        result = self.wait(timeout=0.01)
        # join and wait simply returns after timeout expires
        delay = time.time() - start
        assert 0.01 <= delay < 0.01 + 0.01, delay
        assert result is None, repr(result)

class GenericGetTestCase(TestCase):

    def wait(self, timeout):
        raise NotImplementedError('override me in subclass')

    test_outer_timeout_is_not_lost = test_outer_timeout_is_not_lost

    def test_raises_timeout_number(self):
        start = time.time()
        self.assertRaises(gevent.Timeout, self.wait, timeout=0.01)
        # get raises Timeout after timeout expired
        delay = time.time() - start
        assert 0.01 <= delay < 0.01 + 0.01, delay

    def test_raises_timeout_Timeout(self):
        start = time.time()
        t = gevent.Timeout(0.01)
        try:
            self.wait(timeout=t)
        except gevent.Timeout, ex:
            assert ex is t, (ex, t)
        delay = time.time() - start
        assert 0.01 <= delay < 0.01 + 0.01, delay

    def test_raises_timeout_Timeout_exc_customized(self):
        start = time.time()
        error = RuntimeError('expected error')
        t = gevent.Timeout(0.01, exception=error)
        try:
            self.wait(timeout=t)
        except RuntimeError, ex:
            assert ex is error, (ex, error)
        delay = time.time() - start
        assert 0.01 <= delay < 0.01 + 0.01, delay

