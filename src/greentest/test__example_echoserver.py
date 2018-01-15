from gevent.socket import create_connection, timeout
import greentest
import gevent

import util

_DEFAULT_SOCKET_TIMEOUT = 0.1 if not greentest.EXPECT_POOR_TIMER_RESOLUTION else 2.0


class Test(util.TestServer):
    server = 'echoserver.py'

    def _run_all_tests(self):
        def test_client(message):
            if greentest.PY3:
                kwargs = {'buffering': 1}
            else:
                kwargs = {'bufsize': 1}
            kwargs['mode'] = 'rb'
            conn = create_connection(('127.0.0.1', 16000))
            conn.settimeout(_DEFAULT_SOCKET_TIMEOUT)
            rfile = conn.makefile(**kwargs)

            welcome = rfile.readline()
            assert b'Welcome' in welcome, repr(welcome)

            conn.sendall(message)
            received = rfile.read(len(message))
            self.assertEqual(received, message)

            self.assertRaises(timeout, conn.recv, 1)

            rfile.close()
            conn.close()

        client1 = gevent.spawn(test_client, b'hello\r\n')
        client2 = gevent.spawn(test_client, b'world\r\n')
        gevent.joinall([client1, client2], raise_error=True)


if __name__ == '__main__':
    greentest.main()
