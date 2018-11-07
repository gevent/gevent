import gevent
from gevent import socket
import gevent.testing as greentest


class Test(greentest.TestCase):

    server = None
    acceptor = None
    server_port = None

    def _accept(self):
        self.server.listen(1)
        try:
            conn, _ = self.server.accept()
            self._close_on_teardown(conn)
        except socket.error:
            pass

    def setUp(self):
        super(Test, self).setUp()
        self.server = socket.socket()
        self._close_on_teardown(self.server)
        self.server.bind(('127.0.0.1', 0))
        self.server_port = self.server.getsockname()[1]
        self.acceptor = gevent.spawn(self._accept)
        gevent.sleep(0)

    def tearDown(self):
        if self.acceptor is not None:
            self.acceptor.kill()
            self.acceptor = None
        if self.server is not None:
            self.server.close()
            self.server = None
        super(Test, self).tearDown()

    def test_timeout(self):
        gevent.sleep(0)
        sock = socket.socket()
        self._close_on_teardown(sock)
        sock.connect(('127.0.0.1', self.server_port))

        sock.settimeout(0.1)
        with self.assertRaises(socket.error) as cm:
            sock.recv(1024)

        ex = cm.exception
        self.assertEqual(ex.args, ('timed out',))
        self.assertEqual(str(ex), 'timed out')


if __name__ == '__main__':
    greentest.main()
