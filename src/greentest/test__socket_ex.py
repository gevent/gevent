import gevent.testing as greentest
from gevent import socket
import errno
import sys


class TestClosedSocket(greentest.TestCase):

    switch_expected = False

    def test(self):
        sock = socket.socket()
        sock.close()
        try:
            sock.send(b'a', timeout=1)
            raise AssertionError("Should not get here")
        except (socket.error, OSError) as ex:
            if ex.args[0] != errno.EBADF:
                if sys.platform.startswith('win'):
                    # Windows/Py3 raises "OSError: [WinError 10038] "
                    # which is not standard and not what it does
                    # on Py2.
                    pass
                else:
                    raise


class TestRef(greentest.TestCase):

    switch_expected = False

    def test(self):
        sock = socket.socket()
        assert sock.ref is True, sock.ref
        sock.ref = False
        assert sock.ref is False, sock.ref
        assert sock._read_event.ref is False, sock.ref
        assert sock._write_event.ref is False, sock.ref
        sock.close()


if __name__ == '__main__':
    greentest.main()
