import sys
from gevent import select
import greentest


class TestSelect(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        select.select([], [], [], timeout)


class TestSelectTypes(greentest.TestCase):

    if sys.platform == 'win32':

        def test_int(self):
            import msvcrt
            self.assertRaises(select.error, select.select, [msvcrt.get_osfhandle(1)], [], [], 0.001)
            self.assertRaises(select.error, select.select, [int(msvcrt.get_osfhandle(1))], [], [], 0.001)

        def test_long(self):
            import msvcrt
            self.assertRaises(IOError, select.select, [long(msvcrt.get_osfhandle(1))], [], [], 0.001)

    else:

        def test_int(self):
            select.select([1], [], [], 0.001)

        def test_long(self):
            select.select([1L], [], [], 0.001)

    def test_string(self):
        self.switch_expected = False
        self.assertRaises(TypeError, select.select, ['hello'], [], [], 0.001)


if __name__ == '__main__':
    greentest.main()
