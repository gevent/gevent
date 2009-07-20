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

import greentest
import gevent
from gevent import coros
from greentest import TestCase

DELAY = 0.01

class TestEvent(greentest.TestCase):

    def test_send_exc(self):
        log = []
        e = coros.event()

        def waiter():
            try:
                result = e.wait()
                log.append(('received', result))
            except Exception, ex:
                log.append(('catched', ex))
        gevent.spawn(waiter)
        gevent.sleep(0) # let waiter to block on e.wait()
        obj = Exception()
        e.send(exc=obj)
        gevent.sleep(0)
        assert log == [('catched', obj)], log

    def test_send(self):
        event1 = coros.event()
        event2 = coros.event()

        g = gevent.spawn_later(DELAY/2.0, event1.send, 'hello event1')
        t = gevent.Timeout(0, ValueError('interrupted'))
        try:
            try:
                result = event1.wait()
            except ValueError:
                X = object()
                result = gevent.with_timeout(DELAY, event2.wait, timeout_value=X)
                assert result is X, 'Nobody sent anything to event2 yet it received %r' % (result, )
        finally:
            t.cancel()
            gevent.kill(g, wait=True)


if __name__=='__main__':
    greentest.main()
