from gevent import monkey
monkey.patch_all(subprocess=True)

import sys
from gevent.server import DatagramServer

from gevent.testing.util import run
from gevent.testing import util
from gevent.testing import main

class Test_udp_client(util.TestServer):

    def test(self):
        log = []

        def handle(message, address):
            log.append(message)
            server.sendto(b'reply-from-server', address)

        server = DatagramServer('127.0.0.1:9001', handle)
        server.start()
        try:
            run([sys.executable, '-W', 'ignore', '-u', 'udp_client.py', 'Test_udp_client'],
                timeout=10, cwd=self.cwd)
        finally:
            server.close()
        self.assertEqual(log, [b'Test_udp_client'])


if __name__ == '__main__':
    main()
