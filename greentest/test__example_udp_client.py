from gevent import monkey; monkey.patch_all(subprocess=True)
import sys
from gevent.server import DatagramServer
from unittest import TestCase, main
from util import run


class Test_udp_client(TestCase):

    def test(self):
        log = []

        def handle(message, address):
            log.append(message)
            server.sendto(b'reply-from-server', address)

        server = DatagramServer('127.0.0.1:9000', handle)
        server.start()
        try:
            run([sys.executable, '-u', 'udp_client.py', 'Test_udp_client'], timeout=10, cwd='../examples/')
        finally:
            server.close()
        self.assertEqual(log, [b'Test_udp_client'])


if __name__ == '__main__':
    main()
