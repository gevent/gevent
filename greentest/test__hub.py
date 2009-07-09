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
import time
import gevent
from gevent import core
from gevent import socket

DELAY = 0.1


class TestScheduleCall(greentest.TestCase):

#     def test_local(self):
#         lst = [1]
#         spawn(get_hub().schedule_call_local, DELAY, lst.pop)
#         sleep(DELAY*2)
#         assert lst == [1], lst

    def test_global(self):
        lst = [1]
        gevent.spawn(core.timer, DELAY, lst.pop)
        gevent.sleep(DELAY*2)
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

        assert delay >= DELAY*0.9, 'sleep returned after %s seconds (was scheduled for %s)' % (delay, DELAY)

        def fail():
            1/0

        core.timer(0, fail)

        start = time.time()
        gevent.sleep(DELAY)
        delay = time.time() - start

        assert delay >= DELAY*0.9, 'sleep returned after %s seconds (was scheduled for %s)' % (delay, DELAY)


if __name__=='__main__':
    greentest.main()

