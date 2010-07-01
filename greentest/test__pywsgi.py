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
import sys
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
server_implements_chunked = True
server_implements_pipeline = True
server_implements_100continue = True
DEBUG = '-v' in sys.argv

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
        assert key.lower() not in [x.lower() for x in headers.keys()], 'Header %r:%r sent more than once: %r' % (key, value, headers)
        headers[key] = value
    return response_line, headers


def iread_chunks(fd):
    while True:
        line = fd.readline()
        chunk_size = line.strip()
        try:
            chunk_size = int(chunk_size, 16)
        except:
            print 'Failed to parse chunk size: %r' % line
            raise
        if chunk_size == 0:
            crlf = fd.read(2)
            assert crlf == '\r\n', repr(crlf)
            break
        data = fd.read(chunk_size)
        yield data
        crlf = fd.read(2)
        assert crlf == '\r\n', repr(crlf)


class Response(object):

    def __init__(self, status_line, headers, body=None, chunks=None):
        self.status_line = status_line
        self.headers = headers
        self.body = body
        self.chunks = chunks
        try:
            version, code, self.reason = status_line[:-2].split(' ', 2)
        except Exception:
            print 'Error: %r' % status_line
            raise
        self.code = int(code)
        HTTP, self.version = version.split('/')
        assert HTTP == 'HTTP', repr(HTTP)
        assert self.version in ('1.0', '1.1'), repr(self.version)

    def __iter__(self):
        yield self.status_line
        yield self.headers
        yield self.body

    def __str__(self):
        args = (self.__class__.__name__, self.status_line, self.headers, self.body, self.chunks)
        return '<%s status_line=%r headers=%r body=%r chunks=%r>' % args

    def assertCode(self, code):
        if hasattr(code, '__contains__'):
            assert self.code in code, 'Unexpected code: %r (expected %r)\n%s' % (self.code, code, self)
        else:
            assert self.code == code, 'Unexpected code: %r (expected %r)\n%s' % (self.code, code, self)

    def assertReason(self, reason):
        assert self.reason == reason, 'Unexpected reason: %r (expected %r)\n%s' % (self.reason, reason, self)

    def assertVersion(self, version):
        assert self.version == version, 'Unexpected version: %r (expected %r)\n%s' % (self.version, version, self)

    def assertHeader(self, header, value):
        real_value = self.headers.get(header)
        assert real_value == value, \
               'Unexpected header %r: %r (expected %r)\n%s' % (header, real_value, value, self)

    def assertBody(self, body):
        assert self.body == body, \
               'Unexpected body: %r (expected %r)\n%s' % (self.body, body, self)

    @classmethod
    def read(cls, fd, code=200, reason='default', version='1.1', body=None):
        _status_line, headers = read_headers(fd)
        self = cls(_status_line, headers)
        if code is not None:
            self.assertCode(code)
        if reason == 'default':
            reason = {200: 'OK'}.get(code)
        if reason is not None:
            self.assertReason(reason)
        if version is not None:
            self.assertVersion(version)
        if self.code == 100:
            return self
        try:
            if 'chunked' in headers.get('Transfer-Encoding', ''):
                if CONTENT_LENGTH in headers:
                    print "WARNING: server used chunked transfer-encoding despite having Content-Length header (libevent 1.x's bug)"
                self.chunks = list(iread_chunks(fd))
                self.body = ''.join(self.chunks)
            elif CONTENT_LENGTH in headers:
                num = int(headers[CONTENT_LENGTH])
                self.body = fd.read(num)
            else:
                self.body = fd.read()
        except:
            print 'Response.read failed to read the body:\n%s' % self
            raise
        if body is not None:
            self.assertBody(body)
        return self

read_http = Response.read


class DebugFileObject(object):

    def __init__(self, obj):
        self.obj = obj

    def read(self, *args):
        result = self.obj.read(*args)
        if DEBUG:
            print repr(result)
        return result

    def readline(self, *args):
        result = self.obj.readline(*args)
        if DEBUG:
            print repr(result)
        return result

    def __getattr__(self, item):
        assert item != 'obj'
        return getattr(self.obj, item)


def makefile(self, mode='r', bufsize=-1):
    return DebugFileObject(socket._fileobject(self.dup(), mode, bufsize))

socket.socket.makefile = makefile

class TestCase(greentest.TestCase):

    def get_wsgi_module(self):
        from gevent import pywsgi
        return pywsgi

    validator = staticmethod(validator)

    def init_server(self, application):
        self.server = self.get_wsgi_module().WSGIServer(('127.0.0.1', 0), application)

    def setUp(self):
        application = self.application
        if self.validator is not None:
            application = self.validator(application)
        self.init_server(application)
        self.server.start()
        self.port = self.server.server_port
        greentest.TestCase.setUp(self)

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


class CommonTests(TestCase):

    def test_basic(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd, body='hello world')
        if response.headers.get('Connection') == 'close' and not server_implements_pipeline:
            return
        fd.write('GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd, code=404, reason='Not Found', body='not found')
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd, body='hello world')
        fd.close()

    def test_pipeline(self):
        if not server_implements_pipeline:
            return
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n' + 'GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd, body='hello world')
        exception = AssertionError('HTTP pipelining not supported; the second request is thrown away')
        try:
            timeout = gevent.Timeout.start_new(0.5, exception=exception)
            try:
                read_http(fd, code=404, reason='Not Found', body='not found')
                fd.close()
            finally:
                timeout.cancel()
        except AssertionError, ex:
            if ex is not exception:
                raise

    def test_connection_close(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd)
        if response.headers.get('Connection') == 'close' and not server_implements_pipeline:
            return
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(fd)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        try:
            result = fd.readline()
            assert not result, 'The remote side is expected to close the connection, but it send %r' % (result, )
        except socket.error, ex:
            if ex[0] not in CONN_ABORTED_ERRORS:
                raise

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


class TestNoChunks(CommonTests):
    # when returning a list of strings a shortcut is employed by the server:
    # it calculates the content-length and joins all the chunks before sending
    validator = None

    @staticmethod
    def application(env, start_response):
        path = env['PATH_INFO']
        if path == '/':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            return ['hello ', 'world']
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return ['not ', 'found']

    def test(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd, body='hello world')
        assert response.chunks is None, response.chunks
        response.assertHeader('Content-Length', '11')

        if not server_implements_pipeline:
            fd = self.connect().makefile(bufsize=1)

        fd.write('GET /not-found HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd, code=404, reason='Not Found', body='not found')
        assert response.chunks is None, response.chunks
        response.assertHeader('Content-Length', '9')


class TestExplicitContentLength(TestNoChunks):
    # when returning a list of strings a shortcut is empoyed by the server - it caculates the content-length

    @staticmethod
    def application(env, start_response):
        path = env['PATH_INFO']
        if path == '/':
            start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', '11')])
            return ['hello ', 'world']
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain'), ('Content-Length', '9')])
            return ['not ', 'found']


class TestYield(CommonTests):

    @staticmethod
    def application(env, start_response):
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
        read_http(fd, version='1.0', body='a is a, body is a=a')
        fd.close()


class TestChunkedApp(TestCase):

    chunks = ['this', 'is', 'chunked']

    def body(self):
        return ''.join(self.chunks)

    def application(self, env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        for chunk in self.chunks:
            yield chunk

    def test_chunked_response(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body())
        if server_implements_chunked:
            response.assertHeader('Transfer-Encoding', 'chunked')
            self.assertEqual(response.chunks, self.chunks)
        else:
            response.assertHeader('Transfer-Encoding', None)
            response.assertHeader('Content-Length', str(len(self.body())))
            self.assertEqual(response.chunks, None)

    def test_no_chunked_http_1_0(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, version='1.0')
        self.assertEqual(response.body, self.body())
        self.assertEqual(response.headers.get('Transfer-Encoding'), None)
        content_length = response.headers.get('Content-Length')
        if content_length is not None:
            self.assertEqual(content_length, str(len(self.body())))


class TestBigChunks(TestChunkedApp):
    chunks = ['a' * 8192] * 3


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
        read_http(fd, body='oh hai')

        fd = self.connect().makefile(bufsize=1)
        fd.write('POST /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_http(fd, body='oh hai')

        fd = self.connect().makefile(bufsize=1)
        fd.write('POST /c HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Transfer-Encoding: chunked\r\n\r\n'
                 '2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_http(fd, body='oh hai')


class TestUseWrite(TestCase):

    body = 'abcde'
    end = 'end'
    content_length = str(len(body + end))

    def application(self, env, start_response):
        if env['PATH_INFO'] == '/explicit-content-length':
            write = start_response('200 OK', [('Content-Type', 'text/plain'),
                                              ('Content-Length', self.content_length)])
            write(self.body)
        elif env['PATH_INFO'] == '/no-content-length':
            write = start_response('200 OK', [('Content-Type', 'text/plain')])
            write(self.body)
        elif env['PATH_INFO'] == '/no-content-length-twice':
            write = start_response('200 OK', [('Content-Type', 'text/plain')])
            write(self.body)
            write(self.body)
        else:
            raise Exception('Invalid url')
        return [self.end]

    def test_explicit_content_length(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET /explicit-content-length HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body + self.end)
        response.assertHeader('Content-Length', self.content_length)
        response.assertHeader('Transfer-Encoding', None)

    def test_no_content_length(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET /no-content-length HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body + self.end)
        if server_implements_chunked:
            response.assertHeader('Content-Length', None)
            response.assertHeader('Transfer-Encoding', 'chunked')
        else:
            response.assertHeader('Content-Length', self.content_length)

    def test_no_content_length_twice(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET /no-content-length-twice HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body + self.body + self.end)
        if server_implements_chunked:
            response.assertHeader('Content-Length', None)
            response.assertHeader('Transfer-Encoding', 'chunked')
            assert response.chunks == [self.body, self.body, self.end], response.chunks
        else:
            response.assertHeader('Content-Length', str(5+5+3))


class HttpsTestCase(TestCase):

    certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
    keyfile = os.path.join(os.path.dirname(__file__), 'test_server.key')

    def init_server(self, application):
        self.server = self.get_wsgi_module().WSGIServer(('127.0.0.1', 0), application, certfile=self.certfile, keyfile=self.keyfile)

    def urlopen(self, *args, **kwargs):
        req = HTTPRequest("https://localhost:%s/foo" % self.server.server_port, *args, **kwargs)
        return urllib2.urlopen(req)

    def application(self, environ, start_response):
        assert environ['wsgi.url_scheme'] == 'https', environ['wsgi.url_scheme']
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [environ['wsgi.input'].read()]


class TestHttps(HttpsTestCase):

    if hasattr(socket, 'ssl'):

        def test_012_ssl_server(self):
            result = self.urlopen(method="POST", data='abc').read()
            self.assertEquals(result, 'abc')

        def test_013_empty_return(self):
            result = self.urlopen().read()
            self.assertEquals(result, '')


class TestInternational(TestCase):

    def application(self, environ, start_response):
        assert environ['PATH_INFO'] == '/\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82', environ['PATH_INFO']
        assert environ['QUERY_STRING'] == '%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81=%D0%BE%D1%82%D0%B2%D0%B5%D1%82', environ['QUERY_STRING']
        start_response("200 PASSED", [('Content-Type', 'text/plain')])
        return []

    def test(self):
        sock = self.connect()
        sock.sendall('GET /%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82?%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81=%D0%BE%D1%82%D0%B2%D0%B5%D1%82 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(sock.makefile(), reason='PASSED')


class TestInputReadline(TestCase):
    # this test relies on the fact that readline() returns '' after it reached EOF
    # this behaviour is not mandated by WSGI spec, it's just happens that gevent.wsgi behaves like that
    # as such, this may change in the future

    validator = None

    def application(self, environ, start_response):
        input = environ['wsgi.input']
        lines = []
        while True:
            line = input.readline()
            if not line:
                break
            lines.append(repr(line) + ' ')
        start_response('200 hello', [])
        return lines

    def test(self):
        fd = self.connect().makefile()
        content = 'hello\n\nworld\n123'
        fd.write('POST / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 'Content-Length: %s\r\n\r\n%s' % (len(content), content))
        fd.flush()
        read_http(fd, reason='hello', body="'hello\\n' '\\n' 'world\\n' '123' ")


class TestInputIter(TestInputReadline):

    def application(self, environ, start_response):
        input = environ['wsgi.input']
        lines = []
        for line in input:
            if not line:
                break
            lines.append(repr(line) + ' ')
        start_response('200 hello', [])
        return lines


class TestInputReadlines(TestInputReadline):

    def application(self, environ, start_response):
        input = environ['wsgi.input']
        lines = input.readlines()
        lines = [repr(line) + ' ' for line in lines]
        start_response('200 hello', [])
        return lines


class TestError(TestCase):

    @staticmethod
    def application(env, start_response):
        raise greentest.ExpectedException('TestError.application')

    @property
    def url(self):
        return 'http://127.0.0.1:%s' % self.port

    def test(self):
        try:
            r = urllib2.urlopen(self.url)
            raise AssertionError('Must raise HTTPError, returned %r: %s' % (r, r.code))
        except urllib2.HTTPError, ex:
            assert ex.code == 500, ex
            assert ex.msg == 'Internal Server Error', ex


class TestError_after_start_response(TestError):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        raise greentest.ExpectedException('TestError_after_start_response.application')


class TestEmptyYield(TestCase):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield ""
        yield ""

    def test_err(self):
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        st, h, body = read_http(fd)
        assert body==""

        garbage = fd.read()
        self.assert_(garbage=="", "got garbage: %r" % garbage)


class TestEmptyWrite(TestEmptyYield):
    @staticmethod
    def application(env, start_response):
        write = start_response('200 OK', [('Content-Type', 'text/plain')])
        write("")
        write("")
        return []


class BadRequestTests(TestCase):
    validator = None
    # pywsgi checks content-length, but wsgi does not

    def application(self, env, start_response):
        assert env['CONTENT_LENGTH'] == self.content_length, (env['CONTENT_LENGTH'], self.content_length)
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ['hello']

    def test_negative_content_length(self):
        self.content_length = '-100'
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: %s\r\n\r\n' % self.content_length)
        read_http(fd, code=(200, 400), version=None)

    def test_illegal_content_length(self):
        self.content_length = 'abc'
        fd = self.connect().makefile(bufsize=1)
        fd.write('GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: %s\r\n\r\n' % self.content_length)
        read_http(fd, code=(200, 400), version=None)


class HTTPRequest(urllib2.Request):
    """Hack urllib2.Request to support PUT and DELETE methods."""

    def __init__(self, url, method="GET", data=None, headers={},
                 origin_req_host=None, unverifiable=False):
        urllib2.Request.__init__(self,url,data,headers,origin_req_host,unverifiable)
        self.url = url
        self.method = method

    def get_method(self):
        return self.method


class ChunkedInputTests(TestCase):
    dirt = ""
    validator = None

    def application(self, env, start_response):
        input = env['wsgi.input']
        response = []

        pi = env["PATH_INFO"]

        if pi == "/short-read":
            d = input.read(10)
            response = [d]
        elif pi == "/lines":
            for x in input:
                response.append(x)
        elif pi == "/ping":
            input.read()
            response.append("pong")
        else:
            raise RuntimeError("bad path")

        start_response('200 OK', [('Content-Type', 'text/plain')])
        return response

    def chunk_encode(self, chunks, dirt=None):
        if dirt is None:
            dirt = self.dirt

        b = ""
        for c in chunks:
            b += "%x%s\r\n%s\r\n" % (len(c), dirt, c)
        return b

    def body(self, dirt=None):
        return self.chunk_encode(["this", " is ", "chunked", "\nline", " 2", "\n",  "line3", ""], dirt=dirt)

    def ping(self, fd):
        fd.write("GET /ping HTTP/1.1\r\n\r\n")
        read_http(fd, body="pong")

    def ping_if_possible(self, fd):
        try:
            self.ping(fd)
        except ConnectionClosed:
            if server_implements_pipeline:
                raise
            fd = self.connect().makefile(bufsize=1)
            self.ping(fd)

    def test_short_read_with_content_length(self):
        body = self.body()
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\nContent-Length:1000\r\n\r\n" + body

        fd = self.connect().makefile(bufsize=1)
        fd.write(req)
        read_http(fd, body="this is ch")

        self.ping_if_possible(fd)

    def test_short_read_with_zero_content_length(self):
        body = self.body()
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\nContent-Length:0\r\n\r\n" + body
        print "REQUEST:", repr(req)

        fd = self.connect().makefile(bufsize=1)
        fd.write(req)
        read_http(fd, body="this is ch")

        self.ping_if_possible(fd)

    def test_short_read(self):
        body = self.body()
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\n\r\n" + body

        fd = self.connect().makefile(bufsize=1)
        fd.write(req)
        read_http(fd, body="this is ch")

        self.ping_if_possible(fd)

    def test_dirt(self):
        body = self.body(dirt="; here is dirt\0bla")
        req = "POST /ping HTTP/1.1\r\ntransfer-encoding: Chunked\r\n\r\n" + body

        fd = self.connect().makefile(bufsize=1)
        fd.write(req)
        try:
            read_http(fd, body="pong")
        except AssertionError, ex:
            if str(ex).startswith('Unexpected code: 400'):
                if not server_implements_chunked:
                    print 'ChunkedNotImplementedWarning'
                    return
            raise

        self.ping_if_possible(fd)

    def test_chunked_readline(self):
        body = self.body()
        req = "POST /lines HTTP/1.1\r\nContent-Length: %s\r\ntransfer-encoding: Chunked\r\n\r\n%s" % (len(body), body)

        fd = self.connect().makefile(bufsize=1)
        fd.write(req)
        read_http(fd, body='this is chunked\nline 2\nline3')

    def test_close_before_finished(self):
        self.hook_stderr()
        body = '4\r\nthi'
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\n\r\n" + body
        fd = self.connect().makefile(bufsize=1)
        fd.write(req)
        fd.close()
        gevent.sleep(0.01)
        self.assert_stderr_traceback(IOError, 'unexpected end of file while parsing chunked data')


class Expect100ContinueTests(TestCase):
    validator = None
    def application(self, environ, start_response):
        if int(environ['CONTENT_LENGTH']) > 1024:
            start_response('417 Expectation Failed', [('Content-Length', '7'), ('Content-Type', 'text/plain')])
            return ['failure']
        else:
            text = environ['wsgi.input'].read()
            start_response('200 OK', [('Content-Length', str(len(text))), ('Content-Type', 'text/plain')])
            return [text]

    def test_continue(self):
        fd = self.connect().makefile(bufsize=1)

        fd.write('PUT / HTTP/1.1\r\nHost: localhost\r\nContent-length: 1025\r\nExpect: 100-continue\r\n\r\n')
        try:
            read_http(fd, code=417, body="failure")
        except AssertionError, ex:
            if str(ex).startswith('Unexpected code: 400'):
                if not server_implements_100continue:
                    print '100ContinueNotImplementedWarning'
                    return
            raise


        fd.write('PUT / HTTP/1.1\r\nHost: localhost\r\nContent-length: 7\r\nExpect: 100-continue\r\n\r\ntesting')
        read_http(fd, code=100)
        read_http(fd, body="testing")

del CommonTests

if __name__ == '__main__':
    greentest.main()
