from subprocess import Popen

from gevent import monkey
monkey.patch_all()

import sys
import unittest
from gevent.testing.testcase import SubscriberCleanupMixin

class TestMonkey(SubscriberCleanupMixin, unittest.TestCase):

    maxDiff = None

    def test_time(self):
        import time
        from gevent import time as gtime
        self.assertIs(time.sleep, gtime.sleep)

    def test_thread(self):
        try:
            import thread
        except ImportError:
            import _thread as thread
        import threading

        from gevent import thread as gthread
        self.assertIs(thread.start_new_thread, gthread.start_new_thread)
        self.assertIs(threading._start_new_thread, gthread.start_new_thread)

        # Event patched by default
        self.assertTrue(monkey.is_object_patched('threading', 'Event'))

        if sys.version_info[0] == 2:
            from gevent import threading as gthreading
            from gevent.event import Event as GEvent
            self.assertIs(threading._sleep, gthreading._sleep)
            self.assertTrue(monkey.is_object_patched('threading', '_Event'))
            self.assertIs(threading._Event, GEvent)

    def test_socket(self):
        import socket
        from gevent import socket as gevent_socket
        self.assertIs(socket.create_connection, gevent_socket.create_connection)

    def test_os(self):
        import os
        import types
        from gevent import os as gos
        for name in ('fork', 'forkpty'):
            if hasattr(os, name):
                attr = getattr(os, name)
                self.assertNotIn('built-in', repr(attr))
                self.assertNotIsInstance(attr, types.BuiltinFunctionType)
                self.assertIsInstance(attr, types.FunctionType)
                self.assertIs(attr, getattr(gos, name))

    def test_saved(self):
        self.assertTrue(monkey.saved)
        for modname in monkey.saved:
            self.assertTrue(monkey.is_module_patched(modname))

            for objname in monkey.saved[modname]:
                self.assertTrue(monkey.is_object_patched(modname, objname))

    def test_patch_subprocess_twice(self):
        self.assertNotIn('gevent', repr(Popen))
        self.assertIs(Popen, monkey.get_original('subprocess', 'Popen'))
        monkey.patch_subprocess()
        self.assertIs(Popen, monkey.get_original('subprocess', 'Popen'))

    def test_patch_twice_warnings_events(self):
        import warnings
        from zope.interface import verify

        orig_saved = {}
        for k, v in monkey.saved.items():
            orig_saved[k] = v.copy()

        from gevent import events
        all_events = []
        events.subscribers.append(all_events.append)

        def veto(event):
            if isinstance(event, events.GeventWillPatchModuleEvent) and event.module_name == 'ssl':
                raise events.DoNotPatch

        events.subscribers.append(veto)

        with warnings.catch_warnings(record=True) as issued_warnings:
            # Patch again, triggering three warnings, one for os=False/signal=True,
            # one for repeated monkey-patching, one for patching after ssl (on python >= 2.7.9)
            monkey.patch_all(os=False, extra_kwarg=42)
            self.assertGreaterEqual(len(issued_warnings), 2)
            self.assertIn('SIGCHLD', str(issued_warnings[-1].message))
            self.assertIn('more than once', str(issued_warnings[0].message))

            # Patching with the exact same argument doesn't issue a second warning.
            # in fact, it doesn't do anything
            del issued_warnings[:]
            monkey.patch_all(os=False)
            orig_saved['_gevent_saved_patch_all'] = monkey.saved['_gevent_saved_patch_all']

            self.assertFalse(issued_warnings)

        # Make sure that re-patching did not change the monkey.saved
        # attribute, overwriting the original functions.
        if 'logging' in monkey.saved and 'logging' not in orig_saved:
            # some part of the warning or unittest machinery imports logging
            orig_saved['logging'] = monkey.saved['logging']
        self.assertEqual(orig_saved, monkey.saved)

        # Make sure some problematic attributes stayed correct.
        # NOTE: This was only a problem if threading was not previously imported.
        for k, v in monkey.saved['threading'].items():
            self.assertNotIn('gevent', str(v))

        self.assertIsInstance(all_events[0], events.GeventWillPatchAllEvent)
        self.assertEqual({'extra_kwarg': 42}, all_events[0].patch_all_kwargs)
        verify.verifyObject(events.IGeventWillPatchAllEvent, all_events[0])

        self.assertIsInstance(all_events[1], events.GeventWillPatchModuleEvent)
        verify.verifyObject(events.IGeventWillPatchModuleEvent, all_events[1])

        self.assertIsInstance(all_events[2], events.GeventDidPatchModuleEvent)
        verify.verifyObject(events.IGeventWillPatchModuleEvent, all_events[1])

        self.assertIsInstance(all_events[-2], events.GeventDidPatchBuiltinModulesEvent)
        verify.verifyObject(events.IGeventDidPatchBuiltinModulesEvent, all_events[-2])

        self.assertIsInstance(all_events[-1], events.GeventDidPatchAllEvent)
        verify.verifyObject(events.IGeventDidPatchAllEvent, all_events[-1])

        for e in all_events:
            self.assertFalse(isinstance(e, events.GeventDidPatchModuleEvent)
                             and e.module_name == 'ssl')

    def test_patch_queue(self):
        try:
            import queue
        except ImportError:
            # Python 2 called this Queue. Note that having
            # python-future installed gives us a queue module on
            # Python 2 as well.
            queue = None
        if not hasattr(queue, 'SimpleQueue'):
            raise unittest.SkipTest("Needs SimpleQueue")
        # pylint:disable=no-member
        self.assertIs(queue.SimpleQueue, queue._PySimpleQueue)

if __name__ == '__main__':
    unittest.main()
