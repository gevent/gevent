# @author Donovan Preston, Ryan Williams
#
# Copyright (c) 2000-2007, Linden Research, Inc.
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

from greentest import TestCase, main
import gevent
from gevent import coros

import warnings
warnings.simplefilter('ignore', DeprecationWarning)

class TestEvent(TestCase):
    mode = 'static'

    def test_waiting_for_event(self):
        evt = coros.event()
        value = 'some stuff'
        def send_to_event():
            evt.send(value)
        gevent.spawn(send_to_event)
        self.assertEqual(evt.wait(), value)

    def test_multiple_waiters(self):
        evt = coros.event()
        value = 'some stuff'
        results = []
        def wait_on_event(i_am_done):
            evt.wait()
            results.append(True)
            i_am_done.send()

        waiters = []
        count = 5
        for i in range(count):
            waiters.append(coros.event())
            gevent.spawn(wait_on_event, waiters[-1])
        evt.send()

        for w in waiters:
            w.wait()

        self.assertEqual(len(results), count)

    def test_reset(self):
        evt = coros.event()

        # calling reset before send should throw
        self.assertRaises(AssertionError, evt.reset)

        value = 'some stuff'
        def send_to_event():
            evt.send(value)
        gevent.spawn(send_to_event)
        self.assertEqual(evt.wait(), value)

        # now try it again, and we should get the same exact value,
        # and we shouldn't be allowed to resend without resetting
        value2 = 'second stuff'
        self.assertRaises(AssertionError, evt.send, value2)
        self.assertEqual(evt.wait(), value)

        # reset and everything should be happy
        evt.reset()
        def send_to_event2():
            evt.send(value2)
        gevent.spawn(send_to_event2)
        self.assertEqual(evt.wait(), value2)

    def test_double_exception(self):
        evt = coros.event()
        # send an exception through the event
        evt.send(exc=RuntimeError('from test_double_exception'))
        self.assertRaises(RuntimeError, evt.wait)
        evt.reset()
        # shouldn't see the RuntimeError again
        gevent.Timeout.start_new(0.001, ValueError('from test_double_exception'))
        self.assertRaises(ValueError, evt.wait)


if __name__ == '__main__':
    main()
