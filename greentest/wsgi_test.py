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

import sys
import cgi
import os
import urllib2

import greentest

import gevent
from gevent import wsgi
from gevent import socket


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


def hello_world_explicit_content_length(env, start_response):
    if env['PATH_INFO'] == 'notexist':
        msg = 'not found'
        start_response('404 Not Found',
                       [('Content-type', 'text/plain'),
                        ('Content-Length', len(msg))])
        return [msg]

    msg = 'hello world'
    start_response('200 OK',
                   [('Content-type', 'text/plain'),
                    ('Content-Length', len(msg))])
    return [msg]


def hello_world_yield(env, start_response):
    if env['PATH_INFO'] == 'notexist':
        start_response('404 Not Found', [('Content-type', 'text/plain')])
        yield "not found"
    else:
        start_response('200 OK', [('Content-type', 'text/plain')])
        yield "hello world"


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

    def __init__(self, application):
        self.application = application

    def __call__(self, env, start_response):
        return self.application(env, start_response)


CONTENT_LENGTH = 'content-length'


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
            print 'Failed to split: %r' % (line, )
            raise
        key = key.lower()
        assert key not in headers, 'Header %r is sent more than once' % key
        headers[key.lower()] = value
    return response_line, headers


def iread_chunks(fd):
    while True:
        chunk_size = fd.readline().strip()
        try:
            chunk_size = int(chunk_size, 16)
        except:
            print 'Failed to parse chunk size: %r' % chunk_size
            raise
        if chunk_size == 0:
            crlf = fd.read(2)
            assert crlf == '\r\n', repr(crlf)
            break
        data = fd.read(chunk_size)
        yield data
        crlf = fd.read(2)
        assert crlf == '\r\n', repr(crlf)


def read_http(fd):
    response_line, headers = read_headers(fd)

    if CONTENT_LENGTH in headers:
        num = int(headers[CONTENT_LENGTH])
        body = fd.read(num)
        #print body
    elif 'chunked' in headers.get('transfer-encoding', ''):
        body = ''.join(iread_chunks(fd))
    else:
        body = None

    return response_line, headers, body


class TestCase(greentest.TestCase):

    def listen(self):
        return socket.tcp_listener(('0.0.0.0', 0))

    def setUp(self):
        self.logfile = sys.stderr # StringIO()
        self.site = Site(self.application)
        listener = self.listen()
        self.port = listener.getsockname()[1]
        self.server = gevent.spawn(
            wsgi.server, listener, self.site, max_size=128, log=self.logfile)

    def tearDown(self):
        self.server.kill(block=True)
        # XXX server should have 'close' method which closes everything reliably
        # XXX currently listening socket is kept open


class TestHttpdBasic(TestCase):

    application = staticmethod(hello_world)

    def test_001_server(self):
        sock = socket.connect_tcp(('127.0.0.1', self.port))
        sock.sendall('GET / HTTP/1.0\r\nHost: localhost\r\n\r\n')
        result = sock.makefile().read()
        sock.close()
        ## The server responds with the maximum version it supports
        self.assert_(result.startswith('HTTP'), result)
        self.assert_(result.endswith('hello world'))

    def test_002_keepalive(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd.close()

    def test_003_passing_non_int_to_read(self):
        # This should go in greenio_test
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        cancel = gevent.Timeout.start_new(1, RuntimeError)
        self.assertRaises(TypeError, fd.read, "This shouldn't work")
        cancel.cancel()
        fd.close()

    def test_004_close_keepalive(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        self.assertRaises(ConnectionClosed, read_http, fd)
        fd.close()

    def skip_test_005_run_apachebench(self):
        url = 'http://localhost:%s/' % self.port
        # ab is apachebench
        from gevent import processes
        out = processes.Process(greentest.find_command('ab'),
                                ['-c','64','-n','1024', '-k', url])
        print out.read()

    def test_006_reject_long_urls(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
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

    def test_008_correctresponse(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_200,_,_ = read_http(fd)
        fd.write('GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_404,_,_ = read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_test,_,_ = read_http(fd)
        self.assertEqual(response_line_200,response_line_test)
        fd.close()


class TestExplicitContentLength(TestHttpdBasic):

    application = staticmethod(hello_world_explicit_content_length)


class TestYield(TestHttpdBasic):

    application = staticmethod(hello_world_yield)


class TestGetArg(TestCase):

    def application(self, env, start_response):
        body = env['wsgi.input'].read()
        a = cgi.parse_qs(body).get('a', [1])[0]
        start_response('200 OK', [('Content-type', 'text/plain')])
        return ['a is %s, body is %s' % (a, body)]

    def test_007_get_arg(self):
        # define a new handler that does a get_arg as well as a read_body
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
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


class TestChunkedApp(TestCase):

    application = staticmethod(chunked_app)

    def test_009_chunked_response(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        self.assert_('Transfer-Encoding: chunked' in fd.read())

    def test_010_no_chunked_http_1_0(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        self.assert_('Transfer-Encoding: chunked' not in fd.read())


class TestBigChunks(TestCase):
        
    application = staticmethod(big_chunks)

    def test_011_multiple_chunks(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
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


class TestChunkedPost(TestCase):

    application = staticmethod(chunked_post)

    def test_014_chunked_post(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('PUT /a HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_headers(fd)
        response = fd.read()
        self.assert_(response == 'oh hai', 'invalid response %s' % response)

        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('PUT /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_headers(fd)
        response = fd.read()
        self.assert_(response == 'oh hai', 'invalid response %s' % response)

        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('PUT /c HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        #fd.readuntil('\r\n\r\n')
        read_headers(fd)
        response = fd.read(8192)
        self.assert_(response == 'oh hai', 'invalid response %s' % response)


class TestUseWrite(TestCase):

    application = staticmethod(use_write)

    def test_015_write(self):
        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET /a HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_('content-length' in headers)

        fd = socket.connect_tcp(('127.0.0.1', self.port)).makefile(bufsize=1)
        fd.write('GET /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_('transfer-encoding' in headers)
        self.assert_(headers['transfer-encoding'] == 'chunked')


class TestHttps(greentest.TestCase):

    def application(self, environ, start_response):
        start_response('200 OK', {})
        return [environ['wsgi.input'].read()]

    def test_012_ssl_server(self):

        certificate_file = os.path.join(os.path.dirname(__file__), 'test_server.crt')
        private_key_file = os.path.join(os.path.dirname(__file__), 'test_server.key')

        sock = socket.ssl_listener(('', 4201), private_key_file, certificate_file)

        g = gevent.spawn(wsgi.server, sock, self.application)
        try:
            req = HTTPRequest("https://localhost:4201/foo", method="POST", data='abc')
            f = urllib2.urlopen(req)
            result = f.read()
            self.assertEquals(result, 'abc')
        finally:
            g.kill(block=True)

    def test_013_empty_return(self):
        certificate_file = os.path.join(os.path.dirname(__file__), 'test_server.crt')
        private_key_file = os.path.join(os.path.dirname(__file__), 'test_server.key')
        sock = socket.ssl_listener(('', 4202), private_key_file, certificate_file)
        g = gevent.spawn(wsgi.server, sock, self.application)
        try:
            req = HTTPRequest("https://localhost:4202/foo")
            f = urllib2.urlopen(req)
            result = f.read()
            self.assertEquals(result, '')
        finally:
            g.kill(block=True)


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
    greentest.main()
