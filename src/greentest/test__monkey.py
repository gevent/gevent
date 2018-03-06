from subprocess import Popen

from gevent import monkey
monkey.patch_all()

import sys
import unittest

class TestMonkey(unittest.TestCase):

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

        if sys.version_info[0] == 2:
            from gevent import threading as gthreading
            self.assertIs(threading._sleep, gthreading._sleep)

        # Event patched by default
        self.assertTrue(monkey.is_object_patched('threading', 'Event'))

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
                assert 'built-in' not in repr(attr), repr(attr)
                assert not isinstance(attr, types.BuiltinFunctionType), repr(attr)
                assert isinstance(attr, types.FunctionType), repr(attr)
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

    def test_patch_twice(self):
        import warnings

        orig_saved = {}
        for k, v in monkey.saved.items():
            orig_saved[k] = v.copy()

        with warnings.catch_warnings(record=True) as issued_warnings:
            # Patch again, triggering three warnings, one for os=False/signal=True,
            # one for repeated monkey-patching, one for patching after ssl (on python >= 2.7.9)
            monkey.patch_all(os=False)
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


if __name__ == '__main__':
    unittest.main()
