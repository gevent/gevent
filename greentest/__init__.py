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
import gevent

disabled_marker = '-*-*-*-*-*- disabled -*-*-*-*-*-'
def exit_disabled():
    sys.exit(disabled_marker)

def exit_unless_25():
    if sys.version_info[:2]<(2, 5):
        exit_disabled()

class TestCase(unittest.TestCase):

    __timeout__ = 1
    __switch_check__ = True
    _switch_count = None

    def disable_switch_check(self):
        self._switch_count = None

    def setUp(self):
        gevent.sleep(0) # switch at least once to setup signal handlers
        if hasattr(gevent.core, '_event_count'):
            self._event_count = (gevent.core._event_count(), gevent.core._event_count_active())
        hub = gevent.greenlet.get_hub()
        if hasattr(hub, 'switch_count'):
            self._switch_count = hub.switch_count
        self._timer = gevent.Timeout(self.__timeout__, RuntimeError('test is taking too long'))

    def tearDown(self):
        if hasattr(self, '_timer'):
            self._timer.cancel()
            hub = gevent.greenlet.get_hub()
            if self.__switch_check__ and self._switch_count is not None and hasattr(hub, 'switch_count') and hub.switch_count <= self._switch_count:
                name = getattr(self, '_testMethodName', '') # 2.4 does not have it
                sys.stderr.write('WARNING: %s.%s did not switch\n' % (type(self).__name__, name))
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

_original_Hub = gevent.greenlet.Hub

class CountingHub(_original_Hub):

    switch_count = 0

    def switch(self):
        self.switch_count += 1
        return _original_Hub.switch(self)

gevent.greenlet.Hub = CountingHub
