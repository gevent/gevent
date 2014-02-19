import greentest
import gevent
from gevent import socket
from gevent import backdoor
from six import xrange


def read_until(conn, postfix):
    read = b''
    while not read.endswith(postfix):
        result = conn.recv(1)
        if not result:
            raise AssertionError('Connection ended before %r. Data read:\n%r' % (postfix, read))
        read += result
    return read


def create_connection(address):
    conn = socket.socket()
    conn.connect(address)
    return conn


class Test(greentest.TestCase):

    def test(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()

        def connect():
            conn = create_connection(('127.0.0.1', server.server_port))
            read_until(conn, b'>>> ')
            conn.sendall(b'2+2\r\n')
            line = conn.makefile('rb', 0).readline()
            assert line.strip() == b'4', repr(line)
            read_until(conn, b'>>> ')

        jobs = [gevent.spawn(connect) for _ in xrange(10)]
        gevent.joinall(jobs)
        server.close()
        #self.assertEqual(conn.recv(1), '')

    def test_quit(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            read_until(conn, b'>>> ')
            conn.sendall(b'quit()\r\n')
            line = conn.makefile().read()
            self.assertEqual(line, '')
        finally:
            server.stop()

    def test_sys_exit(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            read_until(conn, b'>>> ')
            conn.sendall(b'import sys; sys.exit(0)\r\n')
            line = conn.makefile().read()
            self.assertEqual(line, '')
        finally:
            server.stop()

    def test_banner(self):
        banner = "Welcome stranger!"
        server = backdoor.BackdoorServer(('127.0.0.1', 0), banner=banner)
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            response = read_until(conn, b'>>> ')
            self.assertEqual(response[:len(banner)], banner.encode())
        finally:
            server.stop()

    def test_builtins(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            read_until(conn, b'>>> ')
            conn.sendall(b'locals()["__builtins__"]\r\n')
            response = read_until(conn, b'>>> ')
            self.assertTrue(len(response) < 300, msg="locals() unusable: %s..." % response[:100])
        finally:
            server.stop()


if __name__ == '__main__':
    greentest.main()
