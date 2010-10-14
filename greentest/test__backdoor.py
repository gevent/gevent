import greentest
import gevent
from gevent import socket
from gevent import backdoor


def read_until(conn, postfix):
    read = ''
    while not read.endswith(postfix):
        result = conn.recv(1)
        if not result:
            raise AssertionError('Connection ended before %r. Data read:\n%r' % (postfix, read))
        read += result
    return read


class Test(greentest.TestCase):

    def test(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()

        def connect():
            conn = socket.create_connection(('127.0.0.1', server.server_port))
            read_until(conn, '>>> ')
            conn.sendall('2+2\r\n')
            line = conn.makefile().readline()
            assert line.strip() == '4', repr(line)

        jobs = [gevent.spawn(connect) for _ in xrange(10)]
        gevent.joinall(jobs)
        server.kill()
        #self.assertEqual(conn.recv(1), '')

    def test_quit(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = socket.create_connection(('127.0.0.1', server.server_port))
            read_until(conn, '>>> ')
            conn.sendall('quit()\r\n')
            line = conn.makefile().read()
            self.assertEqual(line, '')
        finally:
            server.stop()

    def test_sys_exit(self):
        server = backdoor.BackdoorServer(('127.0.0.1', 0))
        server.start()
        try:
            conn = socket.create_connection(('127.0.0.1', server.server_port))
            read_until(conn, '>>> ')
            conn.sendall('import sys; sys.exit(0)\r\n')
            line = conn.makefile().read()
            self.assertEqual(line, '')
        finally:
            server.stop()


if __name__ == '__main__':
    greentest.main()
