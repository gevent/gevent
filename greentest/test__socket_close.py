import gevent
from gevent import socket
from gevent import server
import greentest

# XXX also test: send, sendall, recvfrom, recvfrom_into, sendto


def readall(socket, address):
    while socket.recv(1024):
        pass


class Test(greentest.TestCase):

    error_fatal = False

    def setUp(self):
        self.server = server.StreamServer(('', 0), readall)
        self.server.start()

    def tearDown(self):
        self.server.stop()

    def test_recv_closed(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', self.server.server_port))
        receiver = gevent.spawn(sock.recv, 25)
        try:
            gevent.sleep(0.001)
            sock.close()
            receiver.join(timeout=0.1)
            assert receiver.ready(), receiver
            self.assertEqual(receiver.value, None)
            assert isinstance(receiver.exception, socket.error)
            self.assertEqual(receiver.exception.errno, socket.EBADF)
        finally:
            receiver.kill()

    def test_recv_twice(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', self.server.server_port))
        receiver = gevent.spawn(sock.recv, 25)
        try:
            gevent.sleep(0.001)
            self.assertRaises(AssertionError, sock.recv, 25)
            self.assertRaises(AssertionError, sock.recv, 25)
        finally:
            receiver.kill()


if __name__ == '__main__':
    greentest.main()
