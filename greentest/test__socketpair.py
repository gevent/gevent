from gevent import monkey; monkey.patch_all()
import socket
import unittest


class Test(unittest.TestCase):

    def test(self):
        msg = 'hello world'
        x, y = socket.socketpair()
        x.sendall(msg)
        x.close()
        read = y.makefile().read()
        self.assertEqual(msg, read)

    def test_fromfd(self):
        msg = 'hello world'
        x, y = socket.socketpair()
        xx = socket.fromfd(x.fileno(), x.family, socket.SOCK_STREAM)
        x.close()
        yy = socket.fromfd(y.fileno(), y.family, socket.SOCK_STREAM)
        y.close()

        xx.sendall(msg)
        xx.close()
        read = yy.makefile().read()
        self.assertEqual(msg, read)


if __name__ == '__main__':
    unittest.main()
