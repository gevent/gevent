
from __future__ import absolute_import, print_function, division
import sys
import unittest
import greentest

from gevent import core



class TestCore(unittest.TestCase):

    def test_get_version(self):
        version = core.get_version() # pylint: disable=no-member
        self.assertIsInstance(version, str)
        self.assertTrue(version)
        header_version = core.get_header_version() # pylint: disable=no-member
        self.assertIsInstance(header_version, str)
        self.assertTrue(header_version)
        self.assertEqual(version, header_version)


class TestWatchers(unittest.TestCase):

    def _makeOne(self):
        return core.loop() # pylint:disable=no-member

    def destroyOne(self, loop):
        loop.destroy()

    def setUp(self):
        self.loop = self._makeOne()

    def tearDown(self):
        self.destroyOne(self.loop)
        del self.loop

    def test_io(self):
        if sys.platform == 'win32':
            # libev raises IOError, libuv raises ValueError
            Error = (IOError, ValueError)
            win32 = True
        else:
            Error = ValueError
            win32 = False

        with self.assertRaises(Error):
            self.loop.io(-1, 1)

        if hasattr(core, 'TIMER'):
            # libev
            with self.assertRaises(ValueError):
                self.loop.io(1, core.TIMER) # pylint:disable=no-member

        # Test we can set events and io before it's started
        if not win32:
            # We can't do this with arbitrary FDs on windows;
            # see libev_vfd.h
            io = self.loop.io(1, core.READ) # pylint:disable=no-member
            io.fd = 2
            self.assertEqual(io.fd, 2)
            io.events = core.WRITE # pylint:disable=no-member
            if not hasattr(core, 'libuv'):
                # libev
                # pylint:disable=no-member
                self.assertEqual(core._events_to_str(io.events), 'WRITE|_IOFDSET')
            else:

                self.assertEqual(core._events_to_str(io.events), # pylint:disable=no-member
                                 'WRITE')
            io.start(lambda: None)
            io.close()


    def test_timer_constructor(self):
        with self.assertRaises(ValueError):
            self.loop.timer(1, -1)

    def test_signal_constructor(self):
        with self.assertRaises(ValueError):
            self.loop.signal(1000)

class TestWatchersDefault(TestWatchers):

    def _makeOne(self):
        return core.loop(default=True) # pylint:disable=no-member

    def destroyOne(self, loop):
        return

# XXX: The crash may be fixed? The hang showed up after the crash was
# reproduced and fixed on linux and OS X.
@greentest.skipOnLibuvOnWin(
    "This crashes with PyPy 5.10.0, only on Windows. "
    "See https://ci.appveyor.com/project/denik/gevent/build/1.0.1380/job/lrlvid6mkjtyrhn5#L1103 "
    "It has also timed out, but only on Appveyor CPython 3.6; local CPython 3.6 does not. "
    "See https://ci.appveyor.com/project/denik/gevent/build/1.0.1414/job/yn7yi8b53vtqs8lw#L1523")
class TestWatchersDefaultDestroyed(TestWatchers):

    def _makeOne(self):
        # pylint: disable=no-member
        l = core.loop(default=True)
        l.destroy()
        del l
        return core.loop(default=True)

@greentest.skipOnLibuv("Tests for libev-only functions")
class TestLibev(unittest.TestCase):

    def test_flags_conversion(self):
        # pylint: disable=no-member
        if sys.platform != 'win32':
            self.assertEqual(core.loop(2, default=False).backend_int, 2)
        self.assertEqual(core.loop('select', default=False).backend, 'select')
        self.assertEqual(core._flags_to_int(None), 0)
        self.assertEqual(core._flags_to_int(['kqueue', 'SELECT']), core.BACKEND_KQUEUE | core.BACKEND_SELECT)
        self.assertEqual(core._flags_to_list(core.BACKEND_PORT | core.BACKEND_POLL), ['port', 'poll'])
        self.assertRaises(ValueError, core.loop, ['port', 'blabla'])
        self.assertRaises(TypeError, core.loop, object())


class TestEvents(unittest.TestCase):

    def test_events_conversion(self):
        self.assertEqual(core._events_to_str(core.READ | core.WRITE), # pylint: disable=no-member
                         'READ|WRITE')

    def test_EVENTS(self):
        self.assertEqual(str(core.EVENTS), # pylint: disable=no-member
                         'gevent.core.EVENTS')
        self.assertEqual(repr(core.EVENTS), # pylint: disable=no-member
                         'gevent.core.EVENTS')

if __name__ == '__main__':
    greentest.main()
