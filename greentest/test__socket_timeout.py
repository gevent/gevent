import gevent
from gevent import socket
import unittest


class Test(unittest.TestCase):

    def setUp(self):
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', 0))
        self.server.listen(1)
        self.server_port = self.server.getsockname()[1]
        self.acceptor = gevent.spawn(self.server.accept)

    def tearDown(self):
        self.server.close()
        self.acceptor.kill()
        del self.acceptor
        del self.server

    def test(self):
        sock = socket.socket()
        sock.connect(('127.0.0.1', self.server_port))
        try:
            sock.settimeout(0.1)
            try:
                result = sock.recv(1024)
                raise AssertionError('Expected timeout to be raised, instead recv() returned %r' % (result, ))
            except socket.error, ex:
                self.assertEqual(ex.args, ('timed out',))
                self.assertEqual(str(ex), 'timed out')
                self.assertEqual(ex[0], 'timed out')
        finally:
            sock.close()


if __name__ == '__main__':
    unittest.main()
