import greentest
import socket as real_socket
from gevent import socket

class TestHostname(greentest.TestCase):
    switch_expected = False

    def test_gethostbyname_hostname(self):
        hostname = real_socket.gethostname()
        real_ip = real_socket.gethostbyname(hostname)
        ip = socket.gethostbyname(hostname)
        assert real_ip == ip, (real_ip, ip)

if __name__=='__main__':
    greentest.main()
