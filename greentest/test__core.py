import sys
from greentest import TestCase, main
from gevent import core


class Test(TestCase):
    switch_expected = False
    __timeout__ = None

    def test_get_version(self):
        version = core.get_version()
        assert isinstance(version, str), repr(version)
        assert version, repr(version)
        header_version = core.get_header_version()
        assert isinstance(header_version, str), repr(header_version)
        assert header_version, repr(header_version)
        self.assertEqual(version, header_version)

    def test_flags_conversion(self):
        if sys.platform != 'win32':
            self.assertEqual(core.loop(2, default=False).backend_int, 2)
        self.assertEqual(core.loop('select', default=False).backend, 'select')
        self.assertEqual(core._flags_to_int(None), 0)
        self.assertEqual(core._flags_to_int(['kqueue', 'SELECT']), core.BACKEND_KQUEUE | core.BACKEND_SELECT)
        self.assertEqual(core._flags_to_list(core.BACKEND_PORT | core.BACKEND_POLL), ['port', 'poll'])
        self.assertRaises(ValueError, core.loop, ['port', 'blabla'])
        self.assertRaises(TypeError, core.loop, object())

    def test_events_conversion(self):
        self.assertEqual(core._events_to_str(core.READ | core.WRITE), 'READ|WRITE')

    def test_EVENTS(self):
        self.assertEqual(str(core.EVENTS), 'gevent.core.EVENTS')
        self.assertEqual(repr(core.EVENTS), 'gevent.core.EVENTS')

    def test_io(self):
        if sys.platform == 'win32':
            Error = IOError
        else:
            Error = ValueError
        self.assertRaises(Error, core.loop().io, -1, 1)
        self.assertRaises(ValueError, core.loop().io, 1, core.TIMER)

    def test_timer(self):
        self.assertRaises(ValueError, core.loop().timer, 1, -1)

    def test_signal(self):
        self.assertRaises(ValueError, core.loop().signal, 1000)


if __name__ == '__main__':
    main()
