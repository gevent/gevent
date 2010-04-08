# Copyright (c) 2010 gevent contributors. See LICENSE for details.
import os
import greentest
import gevent
from gevent import server, socket


class TestFatalErrors(greentest.TestCase):

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.ss = server.StreamServer(("127.0.0.1", 0))
        self.ss.pre_start()
        self.socket = self.ss.socket
        self.ss.start()

    def _joinss(self):
        self.ss.join(0.1)
        try:
            self.assert_(self.ss.ready(), "server did not die")
        finally:
            self.ss.kill()

    def test_socket_shutdown(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self._joinss()

    def test_socket_close(self):
        os.close(self.socket.fileno())
        self._joinss()

    def test_socket_file(self):
        os.close(self.socket.fileno())
        f = open("/dev/zero", "r")
        self._joinss()
        del f


if __name__=='__main__':
    greentest.main()
