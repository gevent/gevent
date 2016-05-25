from gevent import monkey; monkey.patch_all()
import os
import sys
import socket
import greentest
# Be careful not to have TestTCP as a bare attribute in this module,
# even aliased, to avoid running duplicate tests
import test__socket
import ssl


class TestSSL(test__socket.TestTCP):

    certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
    privfile = os.path.join(os.path.dirname(__file__), 'test_server.key')
    # Python 2.x has socket.sslerror (which  is an alias for
    # ssl.SSLError); That's gone in Py3 though. In Python 2, most timeouts are raised
    # as SSLError, but Python 3 raises the normal socket.timeout instead. So this has
    # the effect of making TIMEOUT_ERROR be SSLError on Py2 and socket.timeout on Py3
    # See https://bugs.python.org/issue10272
    TIMEOUT_ERROR = getattr(socket, 'sslerror', socket.timeout)

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.listener, _raw_listener = ssl_listener(('127.0.0.1', 0), self.privfile, self.certfile)
        self.port = self.listener.getsockname()[1]

    def create_connection(self, *args, **kwargs):
        return ssl.wrap_socket(super(TestSSL, self).create_connection(*args, **kwargs))

    if not sys.platform.startswith('win32'):

        # The SSL library can take a long time to buffer the large amount of data we're trying
        # to send, so we can't compare to the timeout values
        _test_sendall_timeout_check_time = False

        # The SSL layer has extra buffering, so test_sendall needs
        # to send a very large amount to make it timeout
        _test_sendall_data = data_sent = b'hello' * 100000000

        def test_ssl_sendall_timeout0(self):
            # Issue #317: SSL_WRITE_PENDING in some corner cases

            server_sock = []
            acceptor = test__socket.Thread(target=lambda: server_sock.append(self.listener.accept()))
            client = self.create_connection()
            client.setblocking(False)
            try:
                # Python 3 raises ssl.SSLWantWriteError; Python 2 simply *hangs*
                # on non-blocking sockets because it's a simple loop around
                # send(). Python 2.6 doesn't have SSLWantWriteError
                expected = getattr(ssl, 'SSLWantWriteError', ssl.SSLError)
                self.assertRaises(expected, client.sendall, self._test_sendall_data)
            finally:
                acceptor.join()
                client.close()
                server_sock[0][0].close()

    def test_empty_send(self):
        # Issue 719
        # Sending empty bytes with the 'send' method raises
        # ssl.SSLEOFError in the stdlib. PyPy 4.0 and CPython 2.6
        # both just raise the superclass, ssl.SSLError.
        expected = ssl.SSLError
        self.assertRaises(expected, self._test_sendall,
                          b'',
                          client_method='send')

    def test_sendall_nonblocking(self):
        # Override; doesn't work with SSL sockets.
        pass


def ssl_listener(address, private_key, certificate):
    raw_listener = socket.socket()
    greentest.bind_and_listen(raw_listener, address)
    sock = ssl.wrap_socket(raw_listener, private_key, certificate)
    return sock, raw_listener


if __name__ == '__main__':
    greentest.main()
