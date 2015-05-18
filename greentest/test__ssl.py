from gevent import monkey; monkey.patch_all()
import os
import socket
import greentest
from test__socket import TestTCP
import ssl


class TestSSL(TestTCP):

    certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
    privfile = os.path.join(os.path.dirname(__file__), 'test_server.key')
    # Python 2.x has socket.sslerror, which we need to be sure is an alias for
    # ssl.SSLError. That's gone in Py3 though.
    TIMEOUT_ERROR = getattr(socket, 'sslerror', ssl.SSLError)

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.listener, raw_listener = ssl_listener(('127.0.0.1', 0), self.privfile, self.certfile)
        self.port = self.listener.getsockname()[1]

    def create_connection(self):
        return ssl.wrap_socket(super(TestSSL, self).create_connection())

    def test_sendall_timeout(self):
        pass

del TestTCP


def ssl_listener(address, private_key, certificate):
    raw_listener = socket.socket()
    greentest.bind_and_listen(raw_listener, address)
    sock = ssl.wrap_socket(raw_listener, private_key, certificate)
    return sock, raw_listener


if __name__ == '__main__':
    greentest.main()
