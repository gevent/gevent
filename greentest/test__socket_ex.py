import greentest
from gevent import socket


class TestClosedSocket(greentest.TestCase):

    switch_expected = False

    def test(self):
        sock = socket.socket()
        sock.close()
        try:
            sock.send('a', timeout=1)
        except socket.error, ex:
            if ex[0] != 9:
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


if __name__ == '__main__':
    greentest.main()
