from __future__ import with_statement
from gevent import monkey; monkey.patch_all()
import socket
from time import sleep

import gevent
from gevent.server import StreamServer

import util


class Test_portforwarder(util.TestServer):
    server = 'portforwarder.py'
    args = ['127.0.0.1:10011', '127.0.0.1:10012']

    def after(self):
        self.assertEqual(self.popen.poll(), 0)

    def _run_all_tests(self):
        log = []

        def handle(socket, address):
            while True:
                data = socket.recv(1024)
                print 'got %r' % data
                if not data:
                    break
                log.append(data)

        server = StreamServer(self.args[1], handle)
        server.start()
        try:
            conn = socket.create_connection(('127.0.0.1', 10011))
            conn.sendall('msg1')
            sleep(0.1)
            self.popen.send_signal(15)
            sleep(0.1)
            conn.sendall('msg2')
            conn.close()
            with gevent.Timeout(0.1):
                self.popen.wait()
        finally:
            server.close()

        self.assertEqual(['msg1', 'msg2'], log)


if __name__ == '__main__':
    from unittest import main
    main()
