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
import urllib2
try:
    from wsgiref.validate import validator
except ImportError:
    def validator(app):
        return app

import greentest

import gevent
from gevent import socket


CONTENT_LENGTH = 'Content-Length'
CONN_ABORTED_ERRORS = []

try:
    from errno import WSAECONNABORTED
    CONN_ABORTED_ERRORS.append(WSAECONNABORTED)
except ImportError:
    pass


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
        assert key.lower() not in [x.lower() for x in headers.keys()], 'Header %r is sent more than once: %r' % (key, headers)
        headers[key] = value
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

    if 'chunked' in headers.get('Transfer-Encoding', ''):
        if CONTENT_LENGTH in headers:
            print "WARNING: server used chunked transfer-encoding despite having Content-Length header (libevent 1.x's bug)"
        body = ''.join(iread_chunks(fd))
    elif CONTENT_LENGTH in headers:
        num = int(headers[CONTENT_LENGTH])
        body = fd.read(num)
    else:
        body = None

    return response_line, headers, body


class TestCase(greentest.TestCase):

    def get_wsgi_module(self):
        from gevent import pywsgi
        return pywsgi

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.server = self.get_wsgi_module().WSGIServer(('127.0.0.1', 0), validator(self.application))
        self.server.start()
        self.port = self.server.server_port

    def tearDown(self):
        greentest.TestCase.tearDown(self)
        timeout = gevent.Timeout.start_new(0.5)
        try:
            self.server.stop()
        finally:
            timeout.cancel()
        # XXX currently listening socket is kept open in gevent.wsgi

    def connect(self):
        return socket.create_connection(('127.0.0.1', self.port))


class TestHttpdBasic(TestCase):

    @staticmethod
    def application(env, start_response):
        path = env['PATH_INFO']
        if path == '/':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return ["hello world"]
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return ["not found"]

    def test_001_server(self):
        sock = self.connect()
        sock.sendall('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        result = sock.makefile().read()
        sock.close()
        self.assert_(result.startswith('HTTP/1.1 200 OK\r\n'), result)
        self.assert_(result.endswith('hello world'), result)

    def SKIP_test_002_pipeline(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n' + 'GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        firstline, headers, body = read_http(fd)
        assert firstline == 'HTTP/1.1 200 OK\r\n', repr(firstline)
        assert body == 'hello world', repr(body)
        exception = AssertionError('HTTP pipelining not supported; the second request is thrown away')
        timeout = gevent.Timeout.start_new(0.5, exception=exception)
        try:
            firstline, header, body = read_http(fd)
            assert firstline == 'HTTP/1.1 404 Not Found\r\n', repr(firstline)
            assert body == 'not found', repr(body)
            fd.close()
        finally:
            timeout.cancel()

    def test_003_passing_non_int_to_read(self):
        # This should go in greenio_test
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        cancel = gevent.Timeout.start_new(1, RuntimeError)
        self.assertRaises(TypeError, fd.read, "This shouldn't work")
        cancel.cancel()
        fd.close()

    def test_004_connection_close(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        try:
            result = fd.readline()
            assert not result, 'The remote side is expected to close the connection, but it send %r' % (result, )
        except socket.error, ex:
            if ex[0] not in CONN_ABORTED_ERRORS:
                raise

    def skip_test_005_run_apachebench(self):
        url = 'http://localhost:%s/' % self.port
        # ab is apachebench
        from gevent import processes
        out = processes.Process(greentest.find_command('ab'),
                                ['-c','64','-n','1024', '-k', url])
        print out.read()

    def SKIP_test_006_reject_long_urls(self):
        fd = self.connect().makefile(bufsize=1)
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
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_200, _, _ = read_http(fd)
        fd.write('GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_404, _, _ = read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response_line_test, _, _ = read_http(fd)
        self.assertEqual(response_line_200, response_line_test)
        fd.close()


class TestExplicitContentLength(TestHttpdBasic):

    @staticmethod
    def application(env, start_response):
        path = env['PATH_INFO']
        if path == '/':
            msg = 'hello world'
            start_response('200 OK',
                           [('Content-Type', 'text/plain'),
                            ('Content-Length', str(len(msg)))])
        else:
            msg = 'not found'
            start_response('404 Not Found',
                           [('Content-Type', 'text/plain'),
                            ('Content-Length', str(len(msg)))])
        return [msg]


class TestYield(TestHttpdBasic):

    @staticmethod
    def hello_world_yield(env, start_response):
        path = env['PATH_INFO']
        if path == '/':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            yield "hello world"
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            yield "not found"


class TestGetArg(TestCase):

    @staticmethod
    def application(env, start_response):
        body = env['wsgi.input'].read()
        a = cgi.parse_qs(body).get('a', [1])[0]
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ['a is %s, body is %s' % (a, body)]

    def test_007_get_arg(self):
        # define a new handler that does a get_arg as well as a read_body
        fd = self.connect().makefile(bufsize=1)
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

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield "this"
        yield "is"
        yield "chunked"

    def test_009_chunked_response(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        self.assert_('Transfer-Encoding: chunked' in fd.read())

    def test_010_no_chunked_http_1_0(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        self.assert_('Transfer-Encoding: chunked' not in fd.read())


class TestBigChunks(TestCase):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        line = 'a' * 8192
        for x in range(10):
            yield line


    def test_011_multiple_chunks(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        _, headers = read_headers(fd)
        assert ('Transfer-Encoding', 'chunked') in headers.items(), headers
        chunks = 0
        chunklen = int(fd.readline(), 16)
        while chunklen:
            chunks += 1
            fd.read(chunklen)
            fd.readline()
            chunklen = int(fd.readline(), 16)
        self.assert_(chunks > 1)


class TestChunkedPost(TestCase):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        if env['PATH_INFO'] == '/a':
            data = env['wsgi.input'].read()
            return [data]
        elif env['PATH_INFO'] == '/b':
            return [x for x in iter(lambda: env['wsgi.input'].read(4096), '')]
        elif env['PATH_INFO'] == '/c':
            return [x for x in iter(lambda: env['wsgi.input'].read(1), '')]

    def test_014_chunked_post(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('POST /a HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_(body == 'oh hai', 'invalid response %r' % body)

        fd = self.connect().makefile(bufsize=1)
        fd.write('POST /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_(body == 'oh hai', 'invalid response %r' % body)

        fd = self.connect().makefile(bufsize=1)
        fd.write('POST /c HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_(body == 'oh hai', 'invalid response %r' % body)


class TestUseWrite(TestCase):

    @staticmethod
    def application(env, start_response):
        if env['PATH_INFO'] == '/a':
            write = start_response('200 OK', [('Content-Type', 'text/plain'),
                                              ('Content-Length', '5')])
            write('abcde')
        if env['PATH_INFO'] == '/b':
            write = start_response('200 OK', [('Content-Type', 'text/plain')])
            write('abcde')
        return []

    def test_015_write(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET /a HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response_line, headers, body = read_http(fd)
        self.assert_('Content-Length' in headers)

        fd = self.connect().makefile(bufsize=1)
        fd.write('GET /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response_line, headers, body = read_http(fd)
        #self.assert_('Transfer-Encoding' in headers)
        #self.assert_(headers['Transfer-Encoding'] == 'chunked')


class TestHttps(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def application(self, environ, start_response):
        start_response('200 OK', {})
        return [environ['wsgi.input'].read()]

    def test_012_ssl_server(self):
        certificate_file = os.path.join(os.path.dirname(__file__), 'test_server.crt')
        private_key_file = os.path.join(os.path.dirname(__file__), 'test_server.key')

        sock = socket.ssl_listener(('', 4201), private_key_file, certificate_file)

        g = gevent.spawn(self.get_wsgi_module().server, sock, validator(self.application))
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
        g = gevent.spawn(self.get_wsgi_module().server, sock, validator(self.application))
        try:
            req = HTTPRequest("https://localhost:4202/foo")
            f = urllib2.urlopen(req)
            result = f.read()
            self.assertEquals(result, '')
        finally:
            g.kill(block=True)


class TestInternational(TestCase):

    def application(self, environ, start_response):
        assert environ['PATH_INFO'] == '/\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82', environ['PATH_INFO']
        assert environ['QUERY_STRING'] == '%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81=%D0%BE%D1%82%D0%B2%D0%B5%D1%82', environ['QUERY_STRING']
        start_response("200 PASSED", [('Content-Type', 'text/plain')])
        return []

    def test(self):
        sock = self.connect()
        sock.sendall('GET /%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82?%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81=%D0%BE%D1%82%D0%B2%D0%B5%D1%82 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        result = sock.makefile().read()
        assert '200 PASSED' in result, result


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
