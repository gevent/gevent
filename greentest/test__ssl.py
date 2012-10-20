from gevent import monkey; monkey.patch_all()
import os
import socket
import greentest
from test__socket import TestTCP
import ssl


class TestSSL(TestTCP):

    certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
    privfile = os.path.join(os.path.dirname(__file__), 'test_server.key')
    TIMEOUT_ERROR = socket.sslerror

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.listener, r = ssl_listener(('127.0.0.1', 0), self.privfile, self.certfile)
        self.port = r.getsockname()[1]

    def create_connection(self):
        return ssl.wrap_socket(super(TestSSL, self).create_connection())

    def test_sendall_timeout(self):
        pass

del TestTCP


def ssl_listener(address, private_key, certificate):
    r = socket.socket()
    greentest.bind_and_listen(r, address)
    sock = ssl.wrap_socket(r, private_key, certificate)
    return sock, r


if __name__ == '__main__':
    greentest.main()
