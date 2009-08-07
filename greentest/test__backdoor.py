import greentest
import gevent
from gevent import socket
from gevent import backdoor

class Test(greentest.TestCase):

    def test(self):
        g = gevent.spawn(backdoor.backdoor_server, socket.tcp_listener(('127.0.0.1', 7891)))
        gevent.sleep(0.1)
        s = socket.create_connection(('127.0.0.1', 7891))
        f = s.makefile()
        while True:
            line = gevent.with_timeout(0.1, f.readline, timeout_value=None)
            if line is None:
                break
        s.sendall('2+2\r\n')
        l = f.readline()
        assert l.strip() == '4', repr(l)
        g.kill(block=True)


if __name__ == '__main__':
    greentest.main()
