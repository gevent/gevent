# Copyright 2018 gevent contributors. See LICENSE for details.

import gc
import unittest


from greenlet import gettrace
from greenlet import settrace

from gevent.monkey import get_original
from gevent._compat import thread_mod_name
from gevent._compat import NativeStrIO

from gevent import _monitor as monitor

get_ident = get_original(thread_mod_name, 'get_ident')

class MockHub(object):
    def __init__(self):
        self.thread_ident = get_ident()
        self.exception_stream = NativeStrIO()
        self.dead = False

    def __bool__(self):
        return not self.dead

    __nonzero__ = __bool__

    def handle_error(self, *args): # pylint:disable=unused-argument
        raise # pylint:disable=misplaced-bare-raise

class TestPeriodicMonitoringThread(unittest.TestCase):

    def setUp(self):
        self._orig_start_new_thread = monitor.start_new_thread
        self._orig_thread_sleep = monitor.thread_sleep
        monitor.thread_sleep = lambda _s: gc.collect() # For PyPy
        monitor.start_new_thread = lambda _f, _a: 0xDEADBEEF
        self.hub = MockHub()
        self.pmt = monitor.PeriodicMonitoringThread(self.hub)

    def tearDown(self):
        monitor.start_new_thread = self._orig_start_new_thread
        monitor.thread_sleep = self._orig_thread_sleep
        prev = self.pmt.previous_trace_function
        self.pmt.kill()
        assert gettrace() is prev, (gettrace(), prev)
        settrace(None)

    def test_constructor(self):
        self.assertEqual(0xDEADBEEF, self.pmt.monitor_thread_ident)
        self.assertEqual(gettrace(), self.pmt.greenlet_trace)

    def test_hub_wref(self):
        self.assertIs(self.hub, self.pmt.hub)
        del self.hub

        gc.collect()
        self.assertIsNone(self.pmt.hub)

        # And it killed itself.
        self.assertFalse(self.pmt.should_run)
        self.assertIsNone(gettrace())

    def test_previous_trace(self):
        self.pmt.kill()
        self.assertIsNone(gettrace())

        called = []
        def f(*args):
            called.append(args)

        settrace(f)

        self.pmt = monitor.PeriodicMonitoringThread(self.hub)
        self.assertEqual(gettrace(), self.pmt.greenlet_trace)
        self.assertIs(self.pmt.previous_trace_function, f)

        self.pmt.greenlet_trace('event', 'args')

        self.assertEqual([('event', 'args')], called)

    def test_greenlet_trace(self):
        self.assertEqual(0, self.pmt._greenlet_switch_counter)
        # Unknown event still counts as a switch (should it?)
        self.pmt.greenlet_trace('unknown', None)
        self.assertEqual(1, self.pmt._greenlet_switch_counter)
        self.assertIsNone(self.pmt._active_greenlet)

        origin = object()
        target = object()

        self.pmt.greenlet_trace('switch', (origin, target))
        self.assertEqual(2, self.pmt._greenlet_switch_counter)
        self.assertIs(target, self.pmt._active_greenlet)

        # Unknown event removes active greenlet
        self.pmt.greenlet_trace('unknown', self)
        self.assertEqual(3, self.pmt._greenlet_switch_counter)
        self.assertIsNone(self.pmt._active_greenlet)

    def test_add_monitoring_function(self):

        self.assertRaises(ValueError, self.pmt.add_monitoring_function, None, 1)
        self.assertRaises(ValueError, self.pmt.add_monitoring_function, lambda: None, -1)

        def f():
            pass

        # Add
        self.pmt.add_monitoring_function(f, 1)
        self.assertEqual(2, len(self.pmt.monitoring_functions()))
        self.assertEqual(1, self.pmt.monitoring_functions()[1].period)

        # Update
        self.pmt.add_monitoring_function(f, 2)
        self.assertEqual(2, len(self.pmt.monitoring_functions()))
        self.assertEqual(2, self.pmt.monitoring_functions()[1].period)

        # Remove
        self.pmt.add_monitoring_function(f, None)
        self.assertEqual(1, len(self.pmt.monitoring_functions()))

    def test_calculate_sleep_time(self):
        self.assertEqual(
            self.pmt.monitoring_functions()[0].period,
            self.pmt.calculate_sleep_time())

        # Pretend that GEVENT_CONFIG.max_blocking_time was set to 0,
        # to disable this monitor.
        self.pmt._calculated_sleep_time = 0
        self.assertEqual(
            self.pmt.inactive_sleep_time,
            self.pmt.calculate_sleep_time()
        )

        # Getting the list of monitoring functions will also
        # do this, if it looks like it has changed
        self.pmt.monitoring_functions()[0].period = -1
        self.pmt._calculated_sleep_time = 0
        self.pmt.monitoring_functions()
        self.assertEqual(
            self.pmt.monitoring_functions()[0].period,
            self.pmt.calculate_sleep_time())
        self.assertEqual(
            self.pmt.monitoring_functions()[0].period,
            self.pmt._calculated_sleep_time)


    def test_monitor_blocking(self):
        # Initially there's no active greenlet and no switches,
        # so nothing is considered blocked
        from gevent.events import subscribers
        from gevent.events import IEventLoopBlocked
        from zope.interface.verify import verifyObject
        events = []
        subscribers.append(events.append)

        self.assertFalse(self.pmt.monitor_blocking(self.hub))

        # Give it an active greenlet
        origin = object()
        target = object()
        self.pmt.greenlet_trace('switch', (origin, target))

        # We've switched, so we're not blocked
        self.assertFalse(self.pmt.monitor_blocking(self.hub))
        self.assertFalse(events)

        # Again without switching is a problem.
        self.assertTrue(self.pmt.monitor_blocking(self.hub))
        self.assertTrue(events)
        verifyObject(IEventLoopBlocked, events[0])
        del events[:]

        # But we can order it not to be a problem
        self.pmt.ignore_current_greenlet_blocking()
        self.assertFalse(self.pmt.monitor_blocking(self.hub))
        self.assertFalse(events)

        # And back again
        self.pmt.monitor_current_greenlet_blocking()
        self.assertTrue(self.pmt.monitor_blocking(self.hub))

        # A bad thread_ident in the hub doesn't mess things up
        self.hub.thread_ident = -1
        self.assertTrue(self.pmt.monitor_blocking(self.hub))

    def test_call_destroyed_hub(self):
        # Add a function that destroys the hub so we break out (eventually)
        # This clears the wref, which eventually calls kill()
        def f(_hub):
            _hub = None
            self.hub = None
            gc.collect()

        self.pmt.add_monitoring_function(f, 0.1)
        self.pmt()
        self.assertFalse(self.pmt.should_run)

    def test_call_dead_hub(self):
        # Add a function that makes the hub go false (e.g., it quit)
        # This causes the function to kill itself.
        def f(hub):
            hub.dead = True
        self.pmt.add_monitoring_function(f, 0.1)
        self.pmt()
        self.assertFalse(self.pmt.should_run)

    def test_call_SystemExit(self):
        # breaks the loop
        def f(_hub):
            raise SystemExit()

        self.pmt.add_monitoring_function(f, 0.1)
        self.pmt()

    def test_call_other_error(self):
        class MyException(Exception):
            pass

        def f(_hub):
            raise MyException()

        self.pmt.add_monitoring_function(f, 0.1)
        with self.assertRaises(MyException):
            self.pmt()

if __name__ == '__main__':
    unittest.main()
