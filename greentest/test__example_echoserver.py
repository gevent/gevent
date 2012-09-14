from __future__ import with_statement
from gevent.socket import create_connection, timeout
from unittest import main
import gevent

import util


class Test(util.TestServer):
    server = 'echoserver.py'

    def _run_all_tests(self):
        def test_client(message):
            conn = create_connection(('127.0.0.1', 6000)).makefile(bufsize=1)
            welcome = conn.readline()
            assert 'Welcome' in welcome, repr(welcome)
            conn.write(message)
            received = conn.read(len(message))
            self.assertEqual(received, message)
            conn._sock.settimeout(0.1)
            self.assertRaises(timeout, conn.read, 1)
        client1 = gevent.spawn(test_client, 'hello\r\n')
        client2 = gevent.spawn(test_client, 'world\r\n')
        gevent.joinall([client1, client2], raise_error=True)


if __name__ == '__main__':
    main()
