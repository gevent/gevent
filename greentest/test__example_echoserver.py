from gevent.socket import create_connection, timeout
from unittest import main
import gevent

import util


class Test(util.TestServer):
    server = 'echoserver.py'

    def _run_all_tests(self):
        def test_client(message):
            sock = create_connection(('127.0.0.1', 6000))
            conn = sock.makefile('rwb', 1)
            welcome = conn.readline()
            assert b'Welcome' in welcome, repr(welcome)
            conn.write(message)
            received = conn.read(len(message))
            self.assertEqual(received, message)
            if hasattr(conn, '_sock'):
                conn._sock.settimeout(0.1)
            else:
                sock.settimeout(0.1)

            self.assertRaises(timeout, conn.read, 1)
            conn.close()
            sock.close()
        client1 = gevent.spawn(test_client, b'hello\r\n')
        client2 = gevent.spawn(test_client, b'world\r\n')
        gevent.joinall([client1, client2], raise_error=True)


if __name__ == '__main__':
    main()
