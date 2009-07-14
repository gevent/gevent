# @author Donovan Preston
#
# Copyright (c) 2007, Linden Research, Inc.
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
from gevent import monkey
monkey.patch_all(thread=False)

import cgi
import os
from greentest import TestCase, main
import urllib2

import gevent
from gevent import wsgi
from gevent import socket

from greentest import find_command

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


def hello_world(env, start_response):
    if env['PATH_INFO'] == 'notexist':
        start_response('404 Not Found', [('Content-type', 'text/plain')])
        return ["not found"]

    start_response('200 OK', [('Content-type', 'text/plain')])
    return ["hello world"]


def chunked_app(env, start_response):
    start_response('200 OK', [('Content-type', 'text/plain')])
    yield "this"
    yield "is"
    yield "chunked"


def big_chunks(env, start_response):
    start_response('200 OK', [('Content-type', 'text/plain')])
    line = 'a' * 8192
    for x in range(10):
        yield line

def use_write(env, start_response):
    if env['PATH_INFO'] == '/a':
        write = start_response('200 OK', [('Content-type', 'text/plain'),
                                          ('Content-Length', '5')])
        write('abcde')
    if env['PATH_INFO'] == '/b':
        write = start_response('200 OK', [('Content-type', 'text/plain')])
        write('abcde')
    return []

def chunked_post(env, start_response):
    start_response('200 OK', [('Content-type', 'text/plain')])
    if env['PATH_INFO'] == '/a':
        return [env['wsgi.input'].read()]
    elif env['PATH_INFO'] == '/b':
        return [x for x in iter(lambda: env['wsgi.input'].read(4096), '')]
    elif env['PATH_INFO'] == '/c':
        return [x for x in iter(lambda: env['wsgi.input'].read(1), '')]

class Site(object):
    def __init__(self):
        self.application = hello_world

    def __call__(self, env, start_response):
        return self.application(env, start_response)


CONTENT_LENGTH = 'content-length'


"""
HTTP/1.1 200 OK
Date: foo
Content-length: 11

hello world
"""

class ConnectionClosed(Exception):
    pass


def read_headers(fd):
    response_line = fd.readline()
    if not response_line:
        raise ConnectionClosed
    headers = {}
    while True:
        line = fd.readline().strip()
        if not line:
            break
        try:
            key, value = line.split(': ', 1)
        except:
            print 'bad line:', `line`
            raise
        headers[key.lower()] = value
    return response_line, headers


def read_http(fd):
    response_line, headers = read_headers(fd)

    if CONTENT_LENGTH in headers:
        num = int(headers[CONTENT_LENGTH])
        body = fd.read(num)
        #print body
    else:
        body = None

    return response_line, headers, body


class TestHttpd(TestCase):
    mode = 'static'
    def setUp(self):
        self.logfile = StringIO()
        self.site = Site()
        self.killer = gevent.spawn(
            wsgi.server,
            socket.tcp_listener(('0.0.0.0', 12346)), self.site, max_size=128, log=self.logfile)

    def tearDown(self):
        gevent.kill(self.killer, wait=True)
        gevent.sleep(0) # XXX kill should be enough!

    def test_001_server(self):
        sock = socket.connect_tcp(('127.0.0.1', 12346))
        sock.sendall('GET / HTTP/1.0\r\nHost: localhost\r\n\r\n')
        result = sock.makefile().read()
        sock.close()
        ## The server responds with the maximum version it supports
        self.assert_(result.startswith('HTTP'), result)
        self.assert_(result.endswith('hello world'))

    def test_002_keepalive(self):
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd.close()

    def test_003_passing_non_int_to_read(self):
        # This should go in greenio_test
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        cancel = gevent.Timeout(1, RuntimeError)
        self.assertRaises(TypeError, fd.read, "This shouldn't work")
        cancel.cancel()
        fd.close()

    def test_004_close_keepalive(self):
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        self.assertRaises(ConnectionClosed, read_http, fd)
        fd.close()

    def skip_test_005_run_apachebench(self):
        url = 'http://localhost:12346/'
        # ab is apachebench
        from gevent import processes
        out = processes.Process(find_command('ab'),
                                ['-c','64','-n','1024', '-k', url])
        print out.read()

    def test_006_reject_long_urls(self):
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        path_parts = []
        for ii in range(3000):
            path_parts.append('path')
        path = '/'.join(path_parts)
        request = 'GET /%s HTTP/1.0\r\nHost: localhost\r\n\r\n' % path
        fd.write(request)
        result = fd.readline()
        status = result.split(' ')[1]
        self.assertEqual(status, '414')
        fd.close()

    def test_007_get_arg(self):
        # define a new handler that does a get_arg as well as a read_body
        def new_app(env, start_response):
            body = env['wsgi.input'].read()
            a = cgi.parse_qs(body).get('a', [1])[0]
            start_response('200 OK', [('Content-type', 'text/plain')])
            return ['a is %s, body is %s' % (a, body)]
        self.site.application = new_app
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        request = '\r\n'.join((
            'POST / HTTP/1.0',
            'Host: localhost',
            'Content-Length: 3',
            '',
            'a=a'))
        fd.write(request)

        # send some junk after the actual request
        fd.write('01234567890123456789')
        reqline, headers, body = read_http(fd)
        self.assertEqual(body, 'a is a, body is a=a')
        fd.close()

    def test_008_correctresponse(self):
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_200,_,_ = read_http(fd)
        fd.write('GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_404,_,_ = read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_test,_,_ = read_http(fd)
        self.assertEqual(response_line_200,response_line_test)
        fd.close()

    def test_009_chunked_response(self):
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        self.site.application = chunked_app
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        self.assert_('Transfer-Encoding: chunked' in fd.read())

    def test_010_no_chunked_http_1_0(self):
        self.site.application = chunked_app
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        self.assert_('Transfer-Encoding: chunked' not in fd.read())

    def test_011_multiple_chunks(self):
        self.site.application = big_chunks
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        _, headers = read_headers(fd)
        assert ('transfer-encoding', 'chunked') in headers.items(), headers
        chunks = 0
        chunklen = int(fd.readline(), 16)
        while chunklen:
            chunks += 1
            chunk = fd.read(chunklen)
            fd.readline()
            chunklen = int(fd.readline(), 16)
        self.assert_(chunks > 1)

    def test_014_chunked_post(self):
        self.site.application = chunked_post
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('PUT /a HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_headers(fd)
        response = fd.read()
        self.assert_(response == 'oh hai', 'invalid response %s' % response)

        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('PUT /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_headers(fd)
        response = fd.read()
        self.assert_(response == 'oh hai', 'invalid response %s' % response)

        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('PUT /c HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        #fd.readuntil('\r\n\r\n')
        read_headers(fd)
        response = fd.read(8192)
        self.assert_(response == 'oh hai', 'invalid response %s' % response)

    def test_015_write(self):
        self.site.application = use_write
        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET /a HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_('content-length' in headers)

        fd = socket.connect_tcp(('127.0.0.1', 12346)).makefile(bufsize=1)
        fd.write('GET /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_('transfer-encoding' in headers)
        self.assert_(headers['transfer-encoding'] == 'chunked')


class TestHttps(TestCase):
    mode = 'static'

    def test_012_ssl_server(self):
        def wsgi_app(environ, start_response):
            start_response('200 OK', {})
            return [environ['wsgi.input'].read()]

        certificate_file = os.path.join(os.path.dirname(__file__), 'test_server.crt')
        private_key_file = os.path.join(os.path.dirname(__file__), 'test_server.key')

        sock = socket.ssl_listener(('', 4201), private_key_file, certificate_file)

        g = gevent.spawn(wsgi.server, sock, wsgi_app)
        try:
            req = HTTPRequest("https://localhost:4201/foo", method="POST", data='abc')
            f = urllib2.urlopen(req)
            result = f.read()
            self.assertEquals(result, 'abc')
        finally:
            gevent.kill(g)

    def test_013_empty_return(self):
        def wsgi_app(environ, start_response):
            start_response("200 OK", [])
            return [""]

        certificate_file = os.path.join(os.path.dirname(__file__), 'test_server.crt')
        private_key_file = os.path.join(os.path.dirname(__file__), 'test_server.key')
        sock = socket.ssl_listener(('', 4202), private_key_file, certificate_file)
        g = gevent.spawn(wsgi.server, sock, wsgi_app)
        try:
            req = HTTPRequest("https://localhost:4202/foo")
            f = urllib2.urlopen(req)
            result = f.read()
            self.assertEquals(result, '')
        finally:
            gevent.kill(g)


class HTTPRequest(urllib2.Request):
    """Hack urllib2.Request to support PUT and DELETE methods."""

    def __init__(self, url, method="GET", data=None, headers={},
                 origin_req_host=None, unverifiable=False):
        urllib2.Request.__init__(self,url,data,headers,origin_req_host,unverifiable)
        self.url = url
        self.method = method

    def get_method(self):
        return self.method

if __name__ == '__main__':
    main()
