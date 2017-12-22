# pylint:disable=no-member
import sys
import unittest
from greentest import main, skipOnLibuv
from gevent import core


class TestCore(unittest.TestCase):

    def test_get_version(self):
        version = core.get_version()
        self.assertIsInstance(version, str)
        self.assertTrue(version)
        header_version = core.get_header_version()
        self.assertIsInstance(header_version, str)
        self.assertTrue(header_version)
        self.assertEqual(version, header_version)


class TestWatchers(unittest.TestCase):

    def test_io(self):
        if sys.platform == 'win32':
            # libev raises IOError, libuv raises ValueError
            Error = (IOError, ValueError)
            win32 = True
        else:
            Error = ValueError
            win32 = False
        with self.assertRaises(Error):
            core.loop().io(-1, 1)
        if hasattr(core, 'TIMER'):
            # libev
            with self.assertRaises(ValueError):
                core.loop().io(1, core.TIMER)

        # Test we can set events and io before it's started
        if not win32:
            # We can't do this with arbitrary FDs on windows;
            # see libev_vfd.h
            io = core.loop().io(1, core.READ)
            io.fd = 2
            self.assertEqual(io.fd, 2)
            io.events = core.WRITE
            if not hasattr(core, 'libuv'):
                # libev
                self.assertEqual(core._events_to_str(io.events), 'WRITE|_IOFDSET')
            else:
                self.assertEqual(core._events_to_str(io.events), 'WRITE')
            io.close()

    def test_timer_constructor(self):
        with self.assertRaises(ValueError):
            core.loop().timer(1, -1)

    def test_signal_constructor(self):
        with self.assertRaises(ValueError):
            core.loop().signal(1000)

@skipOnLibuv("Tests for libev-only functions")
class TestLibev(unittest.TestCase):

    def test_flags_conversion(self):
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
        self.assertEqual(core._events_to_str(core.READ | core.WRITE), 'READ|WRITE')

    def test_EVENTS(self):
        self.assertEqual(str(core.EVENTS), 'gevent.core.EVENTS')
        self.assertEqual(repr(core.EVENTS), 'gevent.core.EVENTS')

if __name__ == '__main__':
    main()
