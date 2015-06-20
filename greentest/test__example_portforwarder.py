from __future__ import print_function
from gevent import monkey; monkey.patch_all(subprocess=True)
import sys
import socket
from time import sleep

import gevent
from gevent.server import StreamServer

import util


class Test(util.TestServer):
    server = 'portforwarder.py'
    args = ['127.0.0.1:10011', '127.0.0.1:10012']

    def after(self):
        if sys.platform == 'win32':
            assert self.popen.poll() is not None
        else:
            self.assertEqual(self.popen.poll(), 0)

    def _run_all_tests(self):
        log = []

        def handle(socket, address):
            while True:
                data = socket.recv(1024)
                print('got %r' % data)
                if not data:
                    break
                log.append(data)

        server = StreamServer(self.args[1], handle)
        server.start()
        try:
            conn = socket.create_connection(('127.0.0.1', 10011))
            conn.sendall(b'msg1')
            sleep(0.1)
            self.popen.send_signal(15)
            sleep(0.1)
            try:
                conn.sendall(b'msg2')
                conn.close()
            except socket.error:
                if sys.platform != 'win32':
                    raise
                # On Windows, signal/15 kills the process rather than actually sends a signal
                # so, sendall('msg2') fails with
                # error: [Errno 10054] An existing connection was forcibly closed by the remote host
                # XXX maybe it could be made working with CTRL_C_EVENT somehow?
            with gevent.Timeout(0.1):
                self.popen.wait()
        finally:
            server.close()

        if sys.platform == 'win32':
            self.assertEqual([b'msg1'], log)
        else:
            self.assertEqual([b'msg1', b'msg2'], log)


if __name__ == '__main__':
    from unittest import main
    main()
