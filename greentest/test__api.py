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

import greentest
import gevent
from gevent import util, socket

DELAY = 0.1


class Test(greentest.TestCase):

    def test_killing_dormant(self):
        state = []

        def test():
            try:
                state.append('start')
                gevent.sleep(DELAY)
            except:
                state.append('except')
                # catching GreenletExit
                pass
            state.append('finished')

        g = gevent.spawn(test)
        gevent.sleep(DELAY / 2)
        assert state == ['start'], state
        g.kill()
        # will not get there, unless switching is explicitly scheduled by kill
        assert state == ['start', 'except', 'finished'], state

    def test_nested_with_timeout(self):
        def func():
            return gevent.with_timeout(0.2, gevent.sleep, 2, timeout_value=1)
        self.assertRaises(gevent.Timeout, gevent.with_timeout, 0.1, func)

    def test_sleep_invalid_switch(self):
        p = gevent.spawn(util.wrap_errors(AssertionError, gevent.sleep), 2)
        switcher = gevent.spawn(p.switch, None)
        result = p.get()
        assert isinstance(result, AssertionError), result
        assert 'Invalid switch' in str(result), repr(str(result))
        switcher.kill()

    def test_wait_read_invalid_switch(self):
        p = gevent.spawn(util.wrap_errors(AssertionError, socket.wait_read), 0)
        switcher = gevent.spawn(p.switch, None)
        result = p.get()
        assert isinstance(result, AssertionError), result
        assert 'Invalid switch' in str(result), repr(str(result))
        switcher.kill()

    def test_wait_write_invalid_switch(self):
        p = gevent.spawn(util.wrap_errors(AssertionError, socket.wait_write), 0)
        switcher = gevent.spawn(p.switch, None)
        result = p.get()
        assert isinstance(result, AssertionError), result
        assert 'Invalid switch' in str(result), repr(str(result))
        switcher.kill()


class TestTimers(greentest.TestCase):

    def test_timer_fired(self):
        lst = [1]

        def func():
            gevent.spawn_later(0.01, lst.pop)
            gevent.sleep(0.02)

        gevent.spawn(func)
        assert lst == [1], lst
        gevent.sleep(0.03)
        assert lst == [], lst

    def test_spawn_is_not_cancelled(self):
        lst = [1]

        def func():
            gevent.spawn(lst.pop)
            # exiting immediatelly, but self.lst.pop must be called
        gevent.spawn(func)
        gevent.sleep(0.01)
        assert lst == [], lst


if __name__ == '__main__':
    greentest.main()
