# Copyright (c) 2026 gevent contributors
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

"""
libuv ``run_callback_threadsafe`` must not touch loop watchers off the hub thread.

``uv_check_start`` of the callback timer from a foreign thread races the hub
on Windows and can self-link the check queue. The hub then never returns to
its poll. See https://github.com/gevent/gevent/issues/2212.
"""

import sys
import threading
import time

import gevent
import gevent.testing as greentest
from gevent.hub import get_hub


class _HubLoad(object):
    """Foreign threads queue callbacks while a hub thread heartbeats."""

    def __init__(self):
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.loop = None
        self.beats = 0
        self.executed = 0
        self.stalled = False

    def beat(self):
        while not self.stop.is_set():
            self.beats += 1
            gevent.sleep(0.005)

    def mark_executed(self):
        self.executed += 1

    def hub_main(self):
        self.loop = get_hub().loop
        greenlet = gevent.spawn(self.beat)
        self.ready.set()
        greenlet.join()

    def foreign(self):
        while not self.stop.is_set():
            self.loop.run_callback_threadsafe(self.mark_executed)

    def _watch(self, seconds, stall_s):
        deadline = time.monotonic() + seconds
        last_beats = self.beats
        last_change = time.monotonic()
        while time.monotonic() < deadline:
            time.sleep(0.05)
            current = self.beats
            if current != last_beats:
                last_beats = current
                last_change = time.monotonic()
            elif time.monotonic() - last_change >= stall_s:
                self.stalled = True
                return

    def run(self):
        hub_thread = threading.Thread(target=self.hub_main, daemon=True)
        hub_thread.start()
        if not self.ready.wait(5):
            self.stalled = True
            return hub_thread
        old_interval = sys.getswitchinterval()
        workers = [
            threading.Thread(target=self.foreign, daemon=True)
            for _ in range(4)
        ]
        try:
            sys.setswitchinterval(1e-5)
            for worker in workers:
                worker.start()
            self._watch(1.5, 1.0)
        finally:
            sys.setswitchinterval(old_interval)
            self.stop.set()
        return hub_thread


class TestLibuvThreadsafeCallback(greentest.TestCase):

    def _libuv_loop(self):
        loop = get_hub().loop
        if type(loop).__module__ != 'gevent.libuv.loop':
            self.skipTest('requires the libuv loop')
        return loop

    def test_threadsafe_callback_arms_timer_on_hub_thread(self):
        loop = self._libuv_loop()
        calls = []
        real_setup = loop._setup_for_run_callback

        def recording_setup():
            calls.append(threading.get_ident())
            real_setup()

        ran = []
        foreign_ident = []

        def foreign():
            foreign_ident.append(threading.get_ident())
            loop.run_callback_threadsafe(ran.append, 1)

        loop._setup_for_run_callback = recording_setup
        try:
            worker = threading.Thread(target=foreign)
            worker.start()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            gevent.sleep(0.2)
        finally:
            loop._setup_for_run_callback = real_setup

        self.assertEqual(ran, [1])
        self.assertEqual(foreign_ident, [worker.ident])
        self.assertNotIn(worker.ident, calls)

    def test_foreign_threads_do_not_stall_the_hub(self):
        # The self-link hang is Windows-specific. Every backend still has
        # to keep running callbacks that were queued from native threads,
        # and a stalled hub has to fail this test instead of hanging it.
        load = _HubLoad()
        hub_thread = load.run()
        self.assertFalse(load.stalled)
        self.assertGreater(load.executed, 0)
        hub_thread.join(5)
        self.assertFalse(hub_thread.is_alive())


if __name__ == '__main__':
    greentest.main()
