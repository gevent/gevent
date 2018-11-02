# See issue #466
import unittest
import ctypes


class AnStructure(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int)]


def _send(socket):
    for meth in ('sendall', 'send'):
        anStructure = AnStructure()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('127.0.0.1', 12345))
        getattr(sock, meth)(anStructure)
        sock.close()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(('127.0.0.1', 12345))
        sock.settimeout(1.0)
        getattr(sock, meth)(anStructure)
        sock.close()

class TestSendBuiltinSocket(unittest.TestCase):

    def test_send(self):
        import socket
        _send(socket)


class TestSendGeventSocket(unittest.TestCase):

    def test_send(self):
        import gevent.socket
        _send(gevent.socket)


if __name__ == '__main__':
    unittest.main()
