import greentest
import gevent
from gevent import socket
from gevent import backdoor
from six import xrange


def read_until(conn, postfix):
    read = b''
    if isinstance(postfix, str) and str != bytes:
        postfix = postfix.encode('utf-8')
    while not read.endswith(postfix):
        result = conn.recv(1)
        if not result:
            raise AssertionError('Connection ended before %r. Data read:\n%r' % (postfix, read))
        read += result
    if str != bytes:
        read = read.decode('utf-8')
    return read


def create_connection(address):
    conn = socket.socket()
    conn.connect(address)
    return conn


def readline(conn):
    f = conn.makefile()
    line = f.readline()
    f.close()
    return line


class Test(greentest.TestCase):

    def test(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()

        def connect():
            conn = create_connection(('127.0.0.1', server.server_port))
            try:
                read_until(conn, '>>> ')
                conn.sendall(b'2+2\r\n')
                line = readline(conn)
                self.assertEqual(line.strip(), '4', repr(line))
            finally:
                conn.close()

        try:
            jobs = [gevent.spawn(connect) for _ in xrange(10)]
            gevent.joinall(jobs, raise_error=True)
        finally:
            server.close()
        #self.assertEqual(conn.recv(1), '')

    def test_quit(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            read_until(conn, '>>> ')
            conn.sendall(b'quit()\r\n')
            line = readline(conn)
            self.assertEqual(line, '')
        finally:
            conn.close()
            server.stop()

    def test_sys_exit(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            read_until(conn, b'>>> ')
            conn.sendall(b'import sys; sys.exit(0)\r\n')
            line = readline(conn)
            self.assertEqual(line, '')
        finally:
            conn.close()
            server.stop()

    def test_banner(self):
        banner = "Welcome stranger!" # native string
        server = backdoor.BackdoorServer(('127.0.0.1', 0), banner=banner)
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            response = read_until(conn, b'>>> ')
            self.assertEqual(response[:len(banner)], banner, response)
            conn.close()
        finally:
            server.stop()

    def test_builtins(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = create_connection(('127.0.0.1', server.server_port))
            read_until(conn, b'>>> ')
            conn.sendall(b'locals()["__builtins__"]\r\n')
            response = read_until(conn, '>>> ')
            self.assertTrue(len(response) < 300, msg="locals() unusable: %s..." % response)
        finally:
            conn.close()
            server.stop()


if __name__ == '__main__':
    greentest.main()
