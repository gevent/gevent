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
        server = backdoor.BackdoorServer.spawn(('127.0.0.1', 7891))
        gevent.sleep(0)
        conn = socket.create_connection(('127.0.0.1', 7891))
        read_until(conn, '>>> ')
        conn.sendall('2+2\r\n')
        line = conn.makefile().readline()
        assert line.strip() == '4', repr(line)
        server.kill(block=True)


if __name__ == '__main__':
    greentest.main()
