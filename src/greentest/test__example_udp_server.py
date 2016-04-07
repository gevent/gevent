import socket
from unittest import main
import util


class Test(util.TestServer):
    server = 'udp_server.py'

    def _run_all_tests(self):
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.connect(('127.0.0.1', 9000))
        sock.send(b'Test udp_server')
        data, address = sock.recvfrom(8192)
        self.assertEqual(data, b'Received 15 bytes')
        sock.close()


if __name__ == '__main__':
    main()
