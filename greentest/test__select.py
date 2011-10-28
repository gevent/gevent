import sys
import os
from gevent import select, socket
import greentest


class TestSelect(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        select.select([], [], [], timeout)


if sys.platform != 'win32':

    class TestSelectRead(greentest.GenericWaitTestCase):

        def wait(self, timeout):
            r, w = os.pipe()
            try:
                select.select([r], [], [], timeout)
            finally:
                os.close(r)
                os.close(w)


class TestSelectTypes(greentest.TestCase):

    def test_int(self):
        sock = socket.socket()
        select.select([int(sock.fileno())], [], [], 0.001)

    try:
        long
    except NameError:
        pass
    else:
        def test_long(self):
            sock = socket.socket()
            select.select([long(sock.fileno())], [], [], 0.001)

    def test_string(self):
        self.switch_expected = False
        self.assertRaises(TypeError, select.select, ['hello'], [], [], 0.001)


if __name__ == '__main__':
    greentest.main()
