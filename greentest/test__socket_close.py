import gevent
from gevent import socket
import greentest

# XXX also test: send, sendall, recvfrom, recvfrom_into, sendto

class Test(greentest.TestCase):

    def setUp(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('www.google.com', 80))

    def tearDown(self):
        self.sock.close()

    def test_recv_closed(self):
        receiver = gevent.spawn(self.sock.recv, 25)
        gevent.sleep(0.001)
        self.sock.close()
        receiver.join(timeout=0.001)
        assert receiver.ready(), receiver
        self.assertEqual(receiver.value, '')

    def test_recv_twice(self):
        receiver = gevent.spawn(self.sock.recv, 25)
        gevent.sleep(0.001)
        self.assertRaises(AssertionError, self.sock.recv, 25)
        self.assertRaises(AssertionError, self.sock.recv, 25)
        receiver.kill()


if __name__ == '__main__':
    greentest.main()
