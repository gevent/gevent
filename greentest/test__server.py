# Copyright (c) 2010 gevent contributors. See LICENSE for details.
import os
import greentest
import gevent
from gevent import server, socket


class TestFatalErrors(greentest.TestCase):

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.server = server.StreamServer(("127.0.0.1", 0))
        self.server.start()
        self.socket = self.server.socket

    def _join_server(self):
        self.server.join(0.1)
        try:
            self.assert_(self.server.ready(), "server did not die")
        finally:
            self.server.kill(block=True)

    def test_socket_shutdown(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self._join_server()

    def test_socket_close(self):
        self.socket.close()
        self._join_server()

    def test_socket_close_fileno(self):
        os.close(self.socket.fileno())
        self._join_server()

    def test_socket_file(self):
        os.close(self.socket.fileno())
        f = open("/dev/zero", "r")
        self._join_server()
        del f

    def test_non_fatal_error(self):
        error = socket.error('some non-fatal error')
        self.socket.accept = lambda *args: gevent.getcurrent().throw(error)
        gevent.sleep(0.1)
        assert not self.server.ready()

    def test_dont_keep_reference_on_client_sock(self):
        # the client socket should be garbage collected and closed when handle returns
        self.server.handle = lambda *args: None
        fd = socket.create_connection(('127.0.0.1', self.server.server_port)).makefile(bufsize=1)
        t = gevent.Timeout.start_new(0.1)
        try:
            fd.read()
        finally:
            t.cancel()


if __name__=='__main__':
    greentest.main()
