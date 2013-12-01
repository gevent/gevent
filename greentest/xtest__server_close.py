import unittest
from gevent import socket
import gevent
import errno
import os
from test__server import SimpleStreamServer


class Test(unittest.TestCase):

    ServerSubClass = SimpleStreamServer

    def makefile(self, timeout=0.1, bufsize=1):
        sock = socket.create_connection((self.server.server_host, self.server.server_port))
        sock.settimeout(timeout)
        return sock.makefile(bufsize=bufsize)

    def assertConnectionRefused(self):
        try:
            conn = self.makefile()
            raise AssertionError('Connection was not refused: %r' % (conn._sock, ))
        except socket.error as ex:
            if ex.args[0] != errno.ECONNREFUSED:
                raise

    def assertRequestSucceeded(self):
        conn = self.makefile()
        conn.write('GET /ping HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result.endswith('\r\n\r\nPONG'), repr(result)

    def init_server(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.server.start()
        gevent.sleep(0.01)

    def test_socket_shutdown(self):
        self.init_server()
        self.server.socket.shutdown(socket.SHUT_RDWR)
        self.assertConnectionRefused()
        assert not self.server.started, self.server

    def test_socket_close(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.server.start()
        self.server.socket.close()
        self.assertConnectionRefused()
        #assert not self.server.started

    def test_socket_close_fileno(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.server.start()
        os.close(self.server.socket.fileno())
        self.assertConnectionRefused()
        #assert not self.server.started

    def test_socket_file(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.server.start()
        os.close(self.server.socket.fileno())
        f = open("/dev/zero", "r")
        self.assertConnectionRefused()
        del f


if __name__ == '__main__':
    unittest.main()
