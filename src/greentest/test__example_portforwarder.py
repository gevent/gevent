from __future__ import print_function, absolute_import
from gevent import monkey; monkey.patch_all(subprocess=True)
import signal
import sys
import socket
from time import sleep

import gevent
from gevent.server import StreamServer

import greentest
from greentest import util

@greentest.skipOnLibuvOnCIOnPyPy("Timing issues sometimes lead to connection refused")
class Test(util.TestServer):
    server = 'portforwarder.py'
    args = ['127.0.0.1:10011', '127.0.0.1:10012']

    if sys.platform.startswith('win'):
        from subprocess import CREATE_NEW_PROCESS_GROUP
        # Must be in a new process group to use CTRL_C_EVENT, otherwise
        # we get killed too
        start_kwargs = {'creationflags': CREATE_NEW_PROCESS_GROUP}

    def after(self):
        if sys.platform == 'win32':
            self.assertIsNotNone(self.popen.poll())
        else:
            self.assertEqual(self.popen.poll(), 0)

    def _run_all_tests(self):
        log = []

        def handle(sock, _address):
            while True:
                data = sock.recv(1024)
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
            # On Windows, SIGTERM actually abruptly terminates the process;
            # it can't be caught. However, CTRL_C_EVENT results in a KeyboardInterrupt
            # being raised, so we can shut down properly.
            self.popen.send_signal(getattr(signal, 'CTRL_C_EVENT', signal.SIGTERM))
            sleep(0.1)

            conn.sendall(b'msg2')
            conn.close()

            with gevent.Timeout(2.1):
                self.popen.wait()
        finally:
            server.close()

        self.assertEqual([b'msg1', b'msg2'], log)


if __name__ == '__main__':
    greentest.main()
