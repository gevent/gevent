# Copyright (c) 2007, Linden Research, Inc.
# Copyright (c) 2009-2010 gevent contributors
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
from __future__ import print_function
from gevent import monkey
monkey.patch_all(thread=False)

import cgi
import os
import sys
try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO
try:
    from wsgiref.validate import validator
except ImportError:

    def validator(app):
        return app

import greentest
import gevent
from gevent import socket
from gevent import pywsgi
from gevent.hub import string_types
from gevent.hub import text_type
from gevent.pywsgi import Input


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

REASONS = {200: 'OK',
           500: 'Internal Server Error'}


class ConnectionClosed(Exception):
    pass


def read_headers(fd):
    response_line = fd.readline()
    if not isinstance(response_line, string_types):
        response_line = response_line.decode('iso-8859-1')
    if not response_line:
        raise ConnectionClosed
    headers = {}
    while True:
        line = fd.readline()
        if not isinstance(line, string_types):
            line = line.decode('iso-8859-1')
        line = line.strip()
        if not line:
            break
        try:
            key, value = line.split(': ', 1)
        except:
            print('Failed to split: %r' % (line, ))
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
            print('Failed to parse chunk size: %r' % line)
            raise
        if chunk_size == 0:
            crlf = fd.read(2)
            assert crlf == b'\r\n', repr(crlf)
            break
        data = fd.read(chunk_size)
        yield data
        crlf = fd.read(2)
        assert crlf == b'\r\n', repr(crlf)


class Response(object):

    def __init__(self, status_line, headers):
        self.status_line = status_line
        self.headers = headers
        self.body = None
        self.chunks = False
        try:
            version, code, self.reason = status_line[:-2].split(' ', 2)
        except Exception:
            print('Error: %r' % status_line)
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
        real_value = self.headers.get(header, False)
        assert real_value == value, \
            'Unexpected header %r: %r (expected %r)\n%s' % (header, real_value, value, self)

    def assertBody(self, body):
        assert self.body == body, 'Unexpected body: %r (expected %r)\n%s' % (self.body, body, self)

    @classmethod
    def read(cls, fd, code=200, reason='default', version='1.1', body=None, chunks=None, content_length=None):
        _status_line, headers = read_headers(fd)
        self = cls(_status_line, headers)
        if code is not None:
            self.assertCode(code)
        if reason == 'default':
            reason = REASONS.get(code)
        if reason is not None:
            self.assertReason(reason)
        if version is not None:
            self.assertVersion(version)
        if self.code == 100:
            return self
        if content_length is not None:
            if isinstance(content_length, int):
                content_length = str(content_length)
            self.assertHeader('Content-Length', content_length)
        try:
            if 'chunked' in headers.get('Transfer-Encoding', ''):
                if CONTENT_LENGTH in headers:
                    print("WARNING: server used chunked transfer-encoding despite having Content-Length header (libevent 1.x's bug)")
                self.chunks = list(iread_chunks(fd))
                self.body = b''.join(self.chunks)
            elif CONTENT_LENGTH in headers:
                num = int(headers[CONTENT_LENGTH])
                self.body = fd.read(num)
            else:
                self.body = fd.read()
        except:
            print('Response.read failed to read the body:\n%s' % self)
            raise
        if body is not None:
            self.assertBody(body)
        if chunks is not None:
            assert chunks == self.chunks, (chunks, self.chunks)
        return self

read_http = Response.read


class DebugFileObject(object):

    def __init__(self, obj, line_buffering=False):
        self.obj = obj
        self.line_buffering = line_buffering

    def read(self, *args):
        result = self.obj.read(*args)
        if DEBUG:
            print(repr(result))
        return result

    def readline(self, *args):
        result = self.obj.readline(*args)
        if DEBUG:
            print(repr(result))
        return result

    def write(self, b):
        ret = self.obj.write(b)
        if self.line_buffering:
            self.obj.flush()
        return ret

    def __getattr__(self, item):
        assert item != 'obj'
        return getattr(self.obj, item)


_old_makefile = socket.socket.makefile


def makefile(self, mode='r', bufsize=-1):
    if bufsize == 1 and sys.version_info[0] > 2:
        return DebugFileObject(_old_makefile(self, mode, -1), True)
    else:
        return DebugFileObject(_old_makefile(self, mode, bufsize))

socket.socket.makefile = makefile


class TestCase(greentest.TestCase):

    validator = staticmethod(validator)

    def init_server(self, application):
        self.server = pywsgi.WSGIServer(('127.0.0.1', 0), application)

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

    def makefile(self):
        return self.connect().makefile('rwb', bufsize=1)

    def urlopen(self, *args, **kwargs):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        return read_http(fd, *args, **kwargs)


class CommonTests(TestCase):

    def test_basic(self):
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd, body=b'hello world')
        if response.headers.get('Connection') == 'close' and not server_implements_pipeline:
            return
        fd.write(b'GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd, code=404, reason='Not Found', body=b'not found')
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd, body=b'hello world')
        fd.close()

    def test_pipeline(self):
        if not server_implements_pipeline:
            return
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n' + b'GET /notexist HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd, body=b'hello world')
        exception = AssertionError('HTTP pipelining not supported; the second request is thrown away')
        try:
            timeout = gevent.Timeout.start_new(0.5, exception=exception)
            try:
                read_http(fd, code=404, reason='Not Found', body=b'not found')
                fd.close()
            finally:
                timeout.cancel()
        except AssertionError as ex:
            if ex is not exception:
                raise

    def test_connection_close(self):
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd)
        if response.headers.get('Connection') == 'close' and not server_implements_pipeline:
            return
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(fd)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        try:
            result = fd.readline()
            assert not result, 'The remote side is expected to close the connection, but it send %r' % (result, )
        except socket.error as ex:
            if ex.args[0] not in CONN_ABORTED_ERRORS:
                raise

    def SKIP_test_006_reject_long_urls(self):
        fd = self.makefile()
        path_parts = []
        for ii in range(3000):
            path_parts.append('path')
        path = '/'.join(path_parts)
        request = 'GET /%s HTTP/1.0\r\nHost: localhost\r\n\r\n' % path
        fd.write(request.encode())
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
            return [b'hello ', b'world']
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [b'not ', b'found']

    def test(self):
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd, body=b'hello world')
        assert response.chunks is False, response.chunks
        response.assertHeader('Content-Length', '11')

        if not server_implements_pipeline:
            fd = self.makefile()

        fd.write(b'GET /not-found HTTP/1.1\r\nHost: localhost\r\n\r\n')
        response = read_http(fd, code=404, reason='Not Found', body=b'not found')
        assert response.chunks is False, response.chunks
        response.assertHeader('Content-Length', '9')


class TestExplicitContentLength(TestNoChunks):
    # when returning a list of strings a shortcut is empoyed by the server - it caculates the content-length

    @staticmethod
    def application(env, start_response):
        path = env['PATH_INFO']
        if path == '/':
            start_response('200 OK', [('Content-Type', 'text/plain'), ('Content-Length', '11')])
            return [b'hello ', b'world']
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain'), ('Content-Length', '9')])
            return [b'not ', b'found']


class TestYield(CommonTests):

    @staticmethod
    def application(env, start_response):
        path = env['PATH_INFO']
        if path == '/':
            start_response('200 OK', [('Content-Type', 'text/plain')])
            yield b"hello world"
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            yield b"not found"


if sys.version_info[:2] >= (2, 6):

    class TestBytearray(CommonTests):

        validator = None

        @staticmethod
        def application(env, start_response):
            path = env['PATH_INFO']
            if path == '/':
                start_response('200 OK', [('Content-Type', 'text/plain')])
                return [bytearray(b"hello "), bytearray(b"world")]
            else:
                start_response('404 Not Found', [('Content-Type', 'text/plain')])
                return [bytearray(b"not found")]


class MultiLineHeader(TestCase):
    @staticmethod
    def application(env, start_response):
        assert "test.submit" in env["CONTENT_TYPE"]
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b"ok"]

    def test_multiline_116(self):
        """issue #116"""
        request = '\r\n'.join((
            'POST / HTTP/1.0',
            'Host: localhost',
            'Content-Type: multipart/related; boundary="====XXXX====";',
            ' type="text/xml";start="test.submit"',
            'Content-Length: 0',
            '', ''))
        fd = self.makefile()
        fd.write(request.encode())
        read_http(fd)


class TestGetArg(TestCase):

    @staticmethod
    def application(env, start_response):
        body = env['wsgi.input'].read(None)
        a = cgi.parse_qs(body).get(b'a', [b'1'])[0]
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'a is ' + a + b', body is ' + body]

    def test_007_get_arg(self):
        # define a new handler that does a get_arg as well as a read_body
        fd = self.makefile()
        request = '\r\n'.join((
            'POST / HTTP/1.0',
            'Host: localhost',
            'Content-Length: 3',
            '',
            'a=a'))
        fd.write(request.encode())

        # send some junk after the actual request
        fd.write(b'01234567890123456789')
        read_http(fd, body=b'a is a, body is a=a')
        fd.close()


class TestChunkedApp(TestCase):

    chunks = [b'this', b'is', b'chunked']

    def body(self):
        return b''.join(self.chunks)

    def application(self, env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        for chunk in self.chunks:
            yield chunk

    def test_chunked_response(self):
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body(), chunks=None)
        if server_implements_chunked:
            response.assertHeader('Transfer-Encoding', 'chunked')
            self.assertEqual(response.chunks, self.chunks)
        else:
            response.assertHeader('Transfer-Encoding', False)
            response.assertHeader('Content-Length', str(len(self.body())))
            self.assertEqual(response.chunks, False)

    def test_no_chunked_http_1_0(self):
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd)
        self.assertEqual(response.body, self.body())
        self.assertEqual(response.headers.get('Transfer-Encoding'), None)
        content_length = response.headers.get('Content-Length')
        if content_length is not None:
            self.assertEqual(content_length, str(len(self.body())))


class TestBigChunks(TestChunkedApp):
    chunks = [b'a' * 8192] * 3


class TestChunkedPost(TestCase):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        if env['PATH_INFO'] == '/a':
            data = env['wsgi.input'].read(None)
            return [data]
        elif env['PATH_INFO'] == '/b':
            return [x for x in iter(lambda: env['wsgi.input'].read(4096), b'')]
        elif env['PATH_INFO'] == '/c':
            return [x for x in iter(lambda: env['wsgi.input'].read(1), b'')]

    def test_014_chunked_post(self):
        fd = self.makefile()
        fd.write(b'POST /a HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 b'Transfer-Encoding: chunked\r\n\r\n'
                 b'2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_http(fd, body=b'oh hai')

        fd = self.makefile()
        fd.write(b'POST /b HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 b'Transfer-Encoding: chunked\r\n\r\n'
                 b'2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_http(fd, body=b'oh hai')

        fd = self.makefile()
        fd.write(b'POST /c HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                 b'Transfer-Encoding: chunked\r\n\r\n'
                 b'2\r\noh\r\n4\r\n hai\r\n0\r\n\r\n')
        read_http(fd, body=b'oh hai')


class TestUseWrite(TestCase):

    body = b'abcde'
    end = b'end'
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
        fd = self.makefile()
        fd.write(b'GET /explicit-content-length HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body + self.end)
        response.assertHeader('Content-Length', self.content_length)
        response.assertHeader('Transfer-Encoding', False)

    def test_no_content_length(self):
        fd = self.makefile()
        fd.write(b'GET /no-content-length HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body + self.end)
        if server_implements_chunked:
            response.assertHeader('Content-Length', False)
            response.assertHeader('Transfer-Encoding', 'chunked')
        else:
            response.assertHeader('Content-Length', self.content_length)

    def test_no_content_length_twice(self):
        fd = self.makefile()
        fd.write(b'GET /no-content-length-twice HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        response = read_http(fd, body=self.body + self.body + self.end)
        if server_implements_chunked:
            response.assertHeader('Content-Length', False)
            response.assertHeader('Transfer-Encoding', 'chunked')
            assert response.chunks == [self.body, self.body, self.end], response.chunks
        else:
            response.assertHeader('Content-Length', str(5 + 5 + 3))


class HttpsTestCase(TestCase):

    certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
    keyfile = os.path.join(os.path.dirname(__file__), 'test_server.key')

    def init_server(self, application):
        self.server = pywsgi.WSGIServer(('127.0.0.1', 0), application, certfile=self.certfile, keyfile=self.keyfile)

    def urlopen(self, method='GET', post_body=None, **kwargs):
        import ssl
        sock = self.connect()
        sock = ssl.wrap_socket(sock)
        fd = sock.makefile('rwb', bufsize=1)
        fd.write(('%s / HTTP/1.1\r\nHost: localhost\r\n' % method).encode())
        if post_body is not None:
            fd.write(('Content-Length: %s\r\n\r\n' % len(post_body)).encode())
            fd.write(post_body)
            if kwargs.get('body') is None:
                kwargs['body'] = post_body
        else:
            fd.write(b'\r\n')
        return read_http(fd, **kwargs)

    def application(self, environ, start_response):
        assert environ['wsgi.url_scheme'] == 'https', environ['wsgi.url_scheme']
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [environ['wsgi.input'].read(None)]


class TestHttps(HttpsTestCase):

    if hasattr(socket, 'ssl'):

        def test_012_ssl_server(self):
            result = self.urlopen(method="POST", post_body=b'abc')
            self.assertEquals(result.body, b'abc')

        def test_013_empty_return(self):
            result = self.urlopen()
            self.assertEquals(result.body, b'')


class TestInternational(TestCase):
    validator = None  # wsgiref.validate.IteratorWrapper([]) does not have __len__

    def application(self, environ, start_response):
        path_info = environ['PATH_INFO']
        if isinstance(path_info, text_type):
            path_info = path_info.encode('utf-8')
        assert path_info == b'/\xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82', environ['PATH_INFO']
        assert environ['QUERY_STRING'] == '%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81=%D0%BE%D1%82%D0%B2%D0%B5%D1%82', environ['QUERY_STRING']
        start_response("200 PASSED", [('Content-Type', 'text/plain')])
        return []

    def test(self):
        sock = self.connect()
        sock.sendall(b'''GET /%D0%BF%D1%80%D0%B8%D0%B2%D0%B5%D1%82?%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81=%D0%BE%D1%82%D0%B2%D0%B5%D1%82 HTTP/1.1
Host: localhost
Connection: close

'''.replace(b'\n', b'\r\n'))
        read_http(sock.makefile('rwb'), reason='PASSED', chunks=False, body=b'', content_length=0)


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
            lines.append(repr(line).lstrip('b').encode() + b' ')
        start_response('200 hello', [])
        return lines

    def test(self):
        fd = self.makefile()
        content = 'hello\n\nworld\n123'
        fd.write(('POST / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
                  'Content-Length: %s\r\n\r\n%s' % (len(content), content)).encode())
        fd.flush()
        read_http(fd, reason='hello', body=b"'hello\\n' '\\n' 'world\\n' '123' ")


class TestInputIter(TestInputReadline):

    def application(self, environ, start_response):
        input = environ['wsgi.input']
        lines = []
        for line in input:
            if not line:
                break
            lines.append(repr(line).lstrip('b').encode() + b' ')
        start_response('200 hello', [])
        return lines


class TestInputReadlines(TestInputReadline):

    def application(self, environ, start_response):
        input = environ['wsgi.input']
        lines = input.readlines()
        lines = [repr(line).lstrip('b').encode() + b' ' for line in lines]
        start_response('200 hello', [])
        return lines


class TestInputN(TestCase):
    # testing for this:
    # File "/home/denis/work/gevent/gevent/pywsgi.py", line 70, in _do_read
    #   if length and length > self.content_length - self.position:
    # TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'

    validator = None

    def application(self, environ, start_response):
        environ['wsgi.input'].read(5)
        start_response('200 OK', [])
        return []

    def test(self):
        self.urlopen()


class TestError(TestCase):

    error = greentest.ExpectedException('TestError.application')
    error_fatal = False

    def application(self, env, start_response):
        raise self.error

    def test(self):
        self.expect_one_error()
        self.urlopen(code=500)
        self.assert_error(greentest.ExpectedException, self.error)


class TestError_after_start_response(TestError):

    error = greentest.ExpectedException('TestError_after_start_response.application')

    def application(self, env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        raise self.error


class TestEmptyYield(TestCase):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield b""
        yield b""

    def test_err(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')

        if server_implements_chunked:
            chunks = []
        else:
            chunks = False

        read_http(fd, body=b'', chunks=chunks)

        garbage = fd.read()
        self.assert_(garbage == b"", "got garbage: %r" % garbage)


class TestFirstEmptyYield(TestCase):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield b""
        yield b"hello"

    def test_err(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')

        if server_implements_chunked:
            chunks = [b'hello']
        else:
            chunks = False

        read_http(fd, body=b'hello', chunks=chunks)

        garbage = fd.read()
        self.assert_(garbage == b"", "got garbage: %r" % garbage)


class TestEmptyYield304(TestCase):

    @staticmethod
    def application(env, start_response):
        start_response('304 Not modified', [])
        yield b""
        yield b""

    def test_err(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(fd, code=304, body=b'', chunks=False)
        garbage = fd.read()
        self.assert_(garbage == b"", "got garbage: %r" % garbage)


class TestContentLength304(TestCase):
    validator = None

    def application(self, env, start_response):
        try:
            start_response('304 Not modified', [('Content-Length', '100')])
        except AssertionError as ex:
            start_response('200 Raised', [])
            return [str(ex).encode()]
        else:
            raise AssertionError('start_response did not fail but it should')

    def test_err(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        body = b"Invalid Content-Length for 304 response: '100' (must be absent or zero)"
        read_http(fd, code=200, reason='Raised', body=body, chunks=False)
        garbage = fd.read()
        self.assert_(garbage == b"", "got garbage: %r" % garbage)


class TestBody304(TestCase):
    validator = None

    def application(self, env, start_response):
        start_response('304 Not modified', [])
        return [b'body']

    def test_err(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        try:
            read_http(fd)
        except AssertionError as ex:
            self.assertEqual(str(ex), 'The 304 response must have no body')
        else:
            raise AssertionError('AssertionError must be raised')


class TestWrite304(TestCase):
    validator = None

    def application(self, env, start_response):
        write = start_response('304 Not modified', [])
        self.error_raised = False
        try:
            write(b'body')
        except AssertionError:
            self.error_raised = True
            raise

    def test_err(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        try:
            read_http(fd)
        except AssertionError as ex:
            self.assertEqual(str(ex), 'The 304 response must have no body')
        else:
            raise AssertionError('write() must raise')
        assert self.error_raised, 'write() must raise'


class TestEmptyWrite(TestEmptyYield):

    @staticmethod
    def application(env, start_response):
        write = start_response('200 OK', [('Content-Type', 'text/plain')])
        write(b"")
        write(b"")
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
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(('GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: %s\r\n\r\n' % self.content_length).encode())
        read_http(fd, code=(200, 400))

    def test_illegal_content_length(self):
        self.content_length = 'abc'
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(('GET / HTTP/1.1\r\nHost: localhost\r\nContent-Length: %s\r\n\r\n' % self.content_length).encode())
        read_http(fd, code=(200, 400))


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
            response.append(b"pong")
        else:
            raise RuntimeError("bad path")

        start_response('200 OK', [('Content-Type', 'text/plain')])
        return response

    def chunk_encode(self, chunks, dirt=None):
        if dirt is None:
            dirt = self.dirt

        return chunk_encode(chunks, dirt=dirt)

    def body(self, dirt=None):
        return self.chunk_encode(["this", " is ", "chunked", "\nline", " 2", "\n", "line3", ""], dirt=dirt)

    def ping(self, fd):
        fd.write(b"GET /ping HTTP/1.1\r\n\r\n")
        read_http(fd, body=b"pong")

    def ping_if_possible(self, fd):
        try:
            self.ping(fd)
        except ConnectionClosed:
            if server_implements_pipeline:
                raise
            fd = self.connect().makefile('rwb', bufsize=1)
            self.ping(fd)

    def test_short_read_with_content_length(self):
        body = self.body()
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\nContent-Length:1000\r\n\r\n" + body

        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(req.encode())
        read_http(fd, body=b"this is ch")

        self.ping_if_possible(fd)

    def test_short_read_with_zero_content_length(self):
        body = self.body()
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\nContent-Length:0\r\n\r\n" + body
        print("REQUEST:", repr(req))

        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(req.encode())
        read_http(fd, body=b"this is ch")

        self.ping_if_possible(fd)

    def test_short_read(self):
        body = self.body()
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\n\r\n" + body

        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(req.encode())
        read_http(fd, body=b"this is ch")

        self.ping_if_possible(fd)

    def test_dirt(self):
        body = self.body(dirt="; here is dirt\0bla")
        req = "POST /ping HTTP/1.1\r\ntransfer-encoding: Chunked\r\n\r\n" + body

        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(req.encode())
        try:
            read_http(fd, body=b"pong")
        except AssertionError as ex:
            if str(ex).startswith('Unexpected code: 400'):
                if not server_implements_chunked:
                    print('ChunkedNotImplementedWarning')
                    return
            raise

        self.ping_if_possible(fd)

    def test_chunked_readline(self):
        body = self.body()
        req = "POST /lines HTTP/1.1\r\nContent-Length: %s\r\ntransfer-encoding: Chunked\r\n\r\n%s" % (len(body), body)

        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(req.encode())
        read_http(fd, body=b'this is chunked\nline 2\nline3')

    def test_close_before_finished(self):
        if server_implements_chunked:
            self.expect_one_error()
        body = '4\r\nthi'
        req = "POST /short-read HTTP/1.1\r\ntransfer-encoding: Chunked\r\n\r\n" + body
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(req.encode())
        fd.close()
        gevent.sleep(0.01)
        if server_implements_chunked:
            self.assert_error(IOError, 'unexpected end of file while parsing chunked data')


class Expect100ContinueTests(TestCase):
    validator = None

    def application(self, environ, start_response):
        content_length = int(environ['CONTENT_LENGTH'])
        if content_length > 1024:
            start_response('417 Expectation Failed', [('Content-Length', '7'), ('Content-Type', 'text/plain')])
            return [b'failure']
        else:
            # pywsgi did sent a "100 continue" for each read
            # see http://code.google.com/p/gevent/issues/detail?id=93
            text = environ['wsgi.input'].read(1)
            text += environ['wsgi.input'].read(content_length - 1)
            start_response('200 OK', [('Content-Length', str(len(text))), ('Content-Type', 'text/plain')])
            return [text]

    def test_continue(self):
        fd = self.connect().makefile('rwb', bufsize=1)

        fd.write(b'PUT / HTTP/1.1\r\nHost: localhost\r\nContent-length: 1025\r\nExpect: 100-continue\r\n\r\n')
        try:
            read_http(fd, code=417, body=b"failure")
        except AssertionError as ex:
            if str(ex).startswith('Unexpected code: 400'):
                if not server_implements_100continue:
                    print('100ContinueNotImplementedWarning')
                    return
            raise

        fd.write(b'PUT / HTTP/1.1\r\nHost: localhost\r\nContent-length: 7\r\nExpect: 100-continue\r\n\r\ntesting')
        read_http(fd, code=100)
        read_http(fd, body=b"testing")


class MultipleCookieHeadersTest(TestCase):

    validator = None

    def application(self, environ, start_response):
        self.assertEquals(environ['HTTP_COOKIE'], 'name1="value1"; name2="value2"')
        self.assertEquals(environ['HTTP_COOKIE2'], 'nameA="valueA"; nameB="valueB"')
        start_response('200 OK', [])
        return []

    def test(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b'''GET / HTTP/1.1
Host: localhost
Cookie: name1="value1"
Cookie2: nameA="valueA"
Cookie2: nameB="valueB"
Cookie: name2="value2"\n\n'''.replace(b'\n', b'\r\n'))
        read_http(fd)


class TestLeakInput(TestCase):

    def application(self, environ, start_response):
        pi = environ["PATH_INFO"]
        self._leak_wsgi_input = environ["wsgi.input"]
        self._leak_environ = environ
        if pi == "/leak-frame":
            environ["_leak"] = sys._getframe(0)

        text = b"foobar"
        start_response('200 OK', [('Content-Length', str(len(text))), ('Content-Type', 'text/plain')])
        return [text]

    def test_connection_close_leak_simple(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b"GET / HTTP/1.0\r\nConnection: close\r\n\r\n")
        d = fd.read()
        assert d.startswith(b"HTTP/1.1 200 OK"), "bad response: %r" % d

    def test_connection_close_leak_frame(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        fd.write(b"GET /leak-frame HTTP/1.0\r\nConnection: close\r\n\r\n")
        d = fd.read()
        assert d.startswith(b"HTTP/1.1 200 OK"), "bad response: %r" % d
        self._leak_environ.pop('_leak')


class TestInvalidEnviron(TestCase):
    validator = None
    # check that WSGIServer does not insert any default values for CONTENT_LENGTH

    def application(self, environ, start_response):
        for key, value in environ.items():
            if key in ('CONTENT_LENGTH', 'CONTENT_TYPE') or key.startswith('HTTP_'):
                if key != 'HTTP_HOST':
                    raise AssertionError('Unexpected environment variable: %s=%r' % (key, value))
        start_response('200 OK', [])
        return []

    def test(self):
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.0\r\nHost: localhost\r\n\r\n')
        read_http(fd)
        fd = self.makefile()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\n\r\n')
        read_http(fd)


class Handler(pywsgi.WSGIHandler):

    def read_requestline(self):
        data = self.rfile.read(7)
        if data[0:1] == b'<':
            try:
                data += self.rfile.read(15)
                if data.lower() == b'<policy-file-request/>':
                    self.socket.sendall(b'HELLO')
                else:
                    self.log_error('Invalid request: %r', data)
            finally:
                self.socket.shutdown(socket.SHUT_WR)
                self.rfile.close()
                self.socket.close()
                self.socket = None
        else:
            return data + self.rfile.readline()


class TestSubclass1(TestCase):

    validator = None

    def application(self, environ, start_response):
        start_response('200 OK', [])
        return []

    def init_server(self, application):
        self.server = pywsgi.WSGIServer(('127.0.0.1', 0), application, handler_class=Handler)

    def test(self):
        fd = self.makefile()
        fd.write(b'<policy-file-request/>\x00')
        self.assertEqual(fd.read(), b'HELLO')

        fd = self.makefile()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        read_http(fd)

        fd = self.makefile()
        fd.write(b'<policy-file-XXXuest/>\x00')
        self.assertEqual(fd.read(), b'')


class TestErrorAfterChunk(TestCase):
    validator = None

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield b"hello"
        raise greentest.ExpectedException('TestErrorAfterChunk')

    def test(self):
        fd = self.connect().makefile('rwb', bufsize=1)
        self.expect_one_error()
        fd.write(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: keep-alive\r\n\r\n')
        self.assertRaises(ValueError, read_http, fd)
        self.assert_error(greentest.ExpectedException)


def chunk_encode(chunks, dirt=None):
    if dirt is None:
        dirt = ""

    b = ""
    for c in chunks:
        b += "%x%s\r\n%s\r\n" % (len(c), dirt, c)
    return b


class TestInputRaw(greentest.BaseTestCase):
    def make_input(self, data, content_length=None, chunked_input=False):
        if isinstance(data, list):
            data = chunk_encode(data)
            chunked_input = True

        return Input(BytesIO(data.encode()), content_length=content_length, chunked_input=chunked_input)

    def test_short_post(self):
        i = self.make_input("1", content_length=2)
        self.assertRaises(IOError, i.read)

    def test_short_post_read_with_length(self):
        i = self.make_input("1", content_length=2)
        self.assertRaises(IOError, i.read, 2)

    def test_short_post_readline(self):
        i = self.make_input("1", content_length=2)
        self.assertRaises(IOError, i.readline)

    def test_post(self):
        i = self.make_input("12", content_length=2)
        data = i.read()
        self.assertEqual(data, b"12")

    def test_post_read_with_length(self):
        i = self.make_input("12", content_length=2)
        data = i.read(10)
        self.assertEqual(data, b"12")

    def test_chunked(self):
        i = self.make_input(["1", "2", ""])
        data = i.read()
        self.assertEqual(data, b"12")

    def test_chunked_read_with_length(self):
        i = self.make_input(["1", "2", ""])
        data = i.read(10)
        self.assertEqual(data, b"12")

    def test_chunked_missing_chunk(self):
        i = self.make_input(["1", "2"])
        self.assertRaises(IOError, i.read)

    def test_chunked_missing_chunk_read_with_length(self):
        i = self.make_input(["1", "2"])
        self.assertRaises(IOError, i.read, 10)

    def test_chunked_missing_chunk_readline(self):
        i = self.make_input(["1", "2"])
        self.assertRaises(IOError, i.readline)

    def test_chunked_short_chunk(self):
        i = self.make_input("2\r\n1", chunked_input=True)
        self.assertRaises(IOError, i.read)

    def test_chunked_short_chunk_read_with_length(self):
        i = self.make_input("2\r\n1", chunked_input=True)
        self.assertRaises(IOError, i.read, 2)

    def test_chunked_short_chunk_readline(self):
        i = self.make_input("2\r\n1", chunked_input=True)
        self.assertRaises(IOError, i.readline)


class Test414(TestCase):

    @staticmethod
    def application(env, start_response):
        raise AssertionError('should not get there')

    def test(self):
        fd = self.makefile()
        fd.write(b'''GET /''')
        fd.write(b'x' * 20000)
        fd.write(b''' HTTP/1.0\r\nHello: world\r\n\r\n''')
        read_http(fd, code=414)


del CommonTests

if __name__ == '__main__':
    greentest.main()
