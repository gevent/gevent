import greentest
import gevent
from gevent import socket
from gevent import backdoor


class Test(greentest.TestCase):

    def test(self):
        server = backdoor.BackdoorServer.spawn(('127.0.0.1', 7891))
        gevent.sleep(0.1)
        fileobj = socket.create_connection(('127.0.0.1', 7891)).makefile()
        while True:
            line = gevent.with_timeout(0.1, fileobj.readline, timeout_value=None)
            if line is None:
                break
        fileobj.write('2+2\r\n')
        fileobj.flush()
        line = fileobj.readline()
        assert line.strip() == '4', repr(line)
        server.kill(block=True)


if __name__ == '__main__':
    greentest.main()
