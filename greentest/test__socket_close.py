import gevent
from gevent import socket
import greentest

# XXX also test: send, sendall, recvfrom, recvfrom_into, sendto


class Test(greentest.TestCase):

    def test_recv_closed(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('www.google.com', 80))
        receiver = gevent.spawn(sock.recv, 25)
        gevent.sleep(0.001)
        sock.close()
        receiver.join(timeout=0.001)
        assert receiver.ready(), receiver
        self.assertEqual(receiver.value, '')

    def test_recv_twice(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('www.google.com', 80))
        receiver = gevent.spawn(sock.recv, 25)
        gevent.sleep(0.001)
        self.assertRaises(AssertionError, sock.recv, 25)
        self.assertRaises(AssertionError, sock.recv, 25)
        receiver.kill()


if __name__ == '__main__':
    greentest.main()
