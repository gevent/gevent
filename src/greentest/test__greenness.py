# Copyright (c) 2008 AG Projects
# Author: Denis Bilenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Test than modules in gevent.green package are indeed green.
To do that spawn a green server and then access it using a green socket.
If either operation blocked the whole script would block and timeout.
"""
from gevent import monkey
monkey.patch_all()

import greentest

try:
    import urllib2
except ImportError:
    from urllib import request as urllib2
try:
    import BaseHTTPServer
except ImportError:
    from http import server as BaseHTTPServer

import gevent
from greentest import params


class TestGreenness(greentest.TestCase):
    check_totalrefcount = False

    def setUp(self):
        server_address = params.DEFAULT_BIND_ADDR_TUPLE
        BaseHTTPServer.BaseHTTPRequestHandler.protocol_version = "HTTP/1.0"
        self.httpd = BaseHTTPServer.HTTPServer(server_address, BaseHTTPServer.BaseHTTPRequestHandler)
        self.httpd.request_count = 0

    def tearDown(self):
        self.httpd.server_close()
        self.httpd = None

    def serve(self):
        self.httpd.handle_request()
        self.httpd.request_count += 1

    def test_urllib2(self):
        server = gevent.spawn(self.serve)

        port = self.httpd.socket.getsockname()[1]
        with self.assertRaises(urllib2.HTTPError) as exc:
            urllib2.urlopen('http://127.0.0.1:%s' % port)
        self.assertEqual(exc.exception.code, 501)
        server.get(0.01)
        self.assertEqual(self.httpd.request_count, 1)


if __name__ == '__main__':
    greentest.main()
