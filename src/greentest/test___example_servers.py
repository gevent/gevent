import sys
#import time
from unittest import main
if sys.version_info[0] == 3:
    from urllib import request as urllib2
else:
    import urllib2

import util
import socket
import ssl


class Test_wsgiserver(util.TestServer):
    server = 'wsgiserver.py'
    URL = 'http://127.0.0.1:8088'
    PORT = 8088
    not_found_message = b'<h1>Not Found</h1>'
    ssl_ctx = None
    _use_ssl = False

    def read(self, path='/'):
        url = self.URL + path
        try:
            if self.ssl_ctx is not None:
                response = urllib2.urlopen(url, None, 2, context=self.ssl_ctx)
            else:
                response = urllib2.urlopen(url, None, 2)
        except urllib2.HTTPError:
            response = sys.exc_info()[1]
        result = '%s %s' % (response.code, response.msg), response.read()
        # XXX: It looks like under PyPy this isn't directly closing the socket
        # when SSL is in use. It takes a GC cycle to make that true.
        response.close()
        return result

    def _test_hello(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        self.assertEqual(data, b"<b>hello world</b>")

    def _test_not_found(self):
        status, data = self.read('/xxx')
        self.assertEqual(status, '404 Not Found')
        self.assertEqual(data, self.not_found_message)

    def _do_test_a_blocking_client(self):
        # We spawn this in a separate server because if it's broken
        # the whole server hangs
        print("Checking blocking")
        with self.running_server():
            # First, make sure we can talk to it.
            self._test_hello()
            # Now create a connection and only partway finish
            # the transaction
            sock = socket.create_connection(('127.0.0.1', self.PORT))
            ssl_sock = None
            if self._use_ssl:
                ssl_sock = ssl.wrap_socket(sock)
                sock_file = ssl_sock.makefile(mode='rwb')
            else:
                sock_file = sock.makefile(mode='rwb')
            # write an incomplete request
            sock_file.write(b'GET /xxx HTTP/1.0\r\n')
            sock_file.flush()
            # Leave it open and not doing anything
            # while the other request runs to completion.
            # This demonstrates that a blocking client
            # doesn't hang the whole server
            self._test_hello()

            # now finish the original request
            sock_file.write(b'\r\n')
            sock_file.flush()
            line = sock_file.readline()
            self.assertEqual(line, b'HTTP/1.1 404 Not Found\r\n')

            sock.close()
            sock_file.close()
            if ssl_sock is not None:
                ssl_sock.close()

    def test_a_blocking_client(self):
        self._do_test_a_blocking_client()


class Test_wsgiserver_ssl(Test_wsgiserver):
    server = 'wsgiserver_ssl.py'
    URL = 'https://127.0.0.1:8443'
    PORT = 8443
    _use_ssl = True

    if hasattr(ssl, '_create_unverified_context'):
        # Disable verification for our self-signed cert
        # on Python >= 2.7.9 and 3.4
        ssl_ctx = ssl._create_unverified_context()


class Test_webproxy(Test_wsgiserver):
    server = 'webproxy.py'

    def _run_all_tests(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        assert b"gevent example" in data, repr(data)
        status, data = self.read('/http://www.google.com')
        self.assertEqual(status, '200 OK')
        assert b'google' in data.lower(), repr(data)

    def _do_test_a_blocking_client(self):
        # Not applicable
        return


# class Test_webpy(Test_wsgiserver):
#     server = 'webpy.py'
#     not_found_message = 'not found'
#
#     def _test_hello(self):
#         status, data = self.read('/')
#         self.assertEqual(status, '200 OK')
#         assert "Hello, world" in data, repr(data)
#
#     def _test_long(self):
#         start = time.time()
#         status, data = self.read('/long')
#         delay = time.time() - start
#         assert 10 - 0.5 < delay < 10 + 0.5, delay
#         self.assertEqual(status, '200 OK')
#         self.assertEqual(data, 'Hello, 10 seconds later')


if __name__ == '__main__':
    main()
