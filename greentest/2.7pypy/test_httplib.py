import httplib
import array
import httplib
import StringIO
import socket
import errno

import unittest
TestCase = unittest.TestCase

from test import test_support

HOST = test_support.HOST

class FakeSocket:
    def __init__(self, text, fileclass=StringIO.StringIO, host=None, port=None):
        self.text = text
        self.fileclass = fileclass
        self.data = ''
        self.host = host
        self.port = port

    def sendall(self, data):
        self.data += ''.join(data)

    def makefile(self, mode, bufsize=None):
        if mode != 'r' and mode != 'rb':
            raise httplib.UnimplementedFileMode()
        return self.fileclass(self.text)

    def close(self):
        pass

class EPipeSocket(FakeSocket):

    def __init__(self, text, pipe_trigger):
        # When sendall() is called with pipe_trigger, raise EPIPE.
        FakeSocket.__init__(self, text)
        self.pipe_trigger = pipe_trigger

    def sendall(self, data):
        if self.pipe_trigger in data:
            raise socket.error(errno.EPIPE, "gotcha")
        self.data += data

    def close(self):
        pass

class NoEOFStringIO(StringIO.StringIO):
    """Like StringIO, but raises AssertionError on EOF.

    This is used below to test that httplib doesn't try to read
    more from the underlying file than it should.
    """
    def read(self, n=-1):
        data = StringIO.StringIO.read(self, n)
        if data == '':
            raise AssertionError('caller tried to read past EOF')
        return data

    def readline(self, length=None):
        data = StringIO.StringIO.readline(self, length)
        if data == '':
            raise AssertionError('caller tried to read past EOF')
        return data


class HeaderTests(TestCase):
    def test_auto_headers(self):
        # Some headers are added automatically, but should not be added by
        # .request() if they are explicitly set.

        class HeaderCountingBuffer(list):
            def __init__(self):
                self.count = {}
            def append(self, item):
                kv = item.split(':')
                if len(kv) > 1:
                    # item is a 'Key: Value' header string
                    lcKey = kv[0].lower()
                    self.count.setdefault(lcKey, 0)
                    self.count[lcKey] += 1
                list.append(self, item)

        for explicit_header in True, False:
            for header in 'Content-length', 'Host', 'Accept-encoding':
                conn = httplib.HTTPConnection('example.com')
                conn.sock = FakeSocket('blahblahblah')
                conn._buffer = HeaderCountingBuffer()

                body = 'spamspamspam'
                headers = {}
                if explicit_header:
                    headers[header] = str(len(body))
                conn.request('POST', '/', body, headers)
                self.assertEqual(conn._buffer.count[header.lower()], 1)

    def test_content_length_0(self):

        class ContentLengthChecker(list):
            def __init__(self):
                list.__init__(self)
                self.content_length = None
            def append(self, item):
                kv = item.split(':', 1)
                if len(kv) > 1 and kv[0].lower() == 'content-length':
                    self.content_length = kv[1].strip()
                list.append(self, item)

        # POST with empty body
        conn = httplib.HTTPConnection('example.com')
        conn.sock = FakeSocket(None)
        conn._buffer = ContentLengthChecker()
        conn.request('POST', '/', '')
        self.assertEqual(conn._buffer.content_length, '0',
                        'Header Content-Length not set')

        # PUT request with empty body
        conn = httplib.HTTPConnection('example.com')
        conn.sock = FakeSocket(None)
        conn._buffer = ContentLengthChecker()
        conn.request('PUT', '/', '')
        self.assertEqual(conn._buffer.content_length, '0',
                        'Header Content-Length not set')

    def test_putheader(self):
        conn = httplib.HTTPConnection('example.com')
        conn.sock = FakeSocket(None)
        conn.putrequest('GET','/')
        conn.putheader('Content-length',42)
        self.assertIn('Content-length: 42', conn._buffer)

    def test_ipv6host_header(self):
        # Default host header on IPv6 transaction should wrapped by [] if
        # its actual IPv6 address
        expected = 'GET /foo HTTP/1.1\r\nHost: [2001::]:81\r\n' \
                   'Accept-Encoding: identity\r\n\r\n'
        conn = httplib.HTTPConnection('[2001::]:81')
        sock = FakeSocket('')
        conn.sock = sock
        conn.request('GET', '/foo')
        self.assertTrue(sock.data.startswith(expected))

        expected = 'GET /foo HTTP/1.1\r\nHost: [2001:102A::]\r\n' \
                   'Accept-Encoding: identity\r\n\r\n'
        conn = httplib.HTTPConnection('[2001:102A::]')
        sock = FakeSocket('')
        conn.sock = sock
        conn.request('GET', '/foo')
        self.assertTrue(sock.data.startswith(expected))


class BasicTest(TestCase):
    def test_status_lines(self):
        # Test HTTP status lines

        body = "HTTP/1.1 200 Ok\r\n\r\nText"
        sock = FakeSocket(body)
        resp = httplib.HTTPResponse(sock)
        resp.begin()
        self.assertEqual(resp.read(0), '')  # Issue #20007
        self.assertFalse(resp.isclosed())
        self.assertEqual(resp.read(), 'Text')
        self.assertTrue(resp.isclosed())

        body = "HTTP/1.1 400.100 Not Ok\r\n\r\nText"
        sock = FakeSocket(body)
        resp = httplib.HTTPResponse(sock)
        self.assertRaises(httplib.BadStatusLine, resp.begin)

    def test_bad_status_repr(self):
        exc = httplib.BadStatusLine('')
        self.assertEqual(repr(exc), '''BadStatusLine("\'\'",)''')

    def test_partial_reads(self):
        # if we have a length, the system knows when to close itself
        # same behaviour than when we read the whole thing with read()
        body = "HTTP/1.1 200 Ok\r\nContent-Length: 4\r\n\r\nText"
        sock = FakeSocket(body)
        resp = httplib.HTTPResponse(sock)
        resp.begin()
        self.assertEqual(resp.read(2), 'Te')
        self.assertFalse(resp.isclosed())
        self.assertEqual(resp.read(2), 'xt')
        self.assertTrue(resp.isclosed())

    def test_partial_reads_no_content_length(self):
        # when no length is present, the socket should be gracefully closed when
        # all data was read
        body = "HTTP/1.1 200 Ok\r\n\r\nText"
        sock = FakeSocket(body)
        resp = httplib.HTTPResponse(sock)
        resp.begin()
        self.assertEqual(resp.read(2), 'Te')
        self.assertFalse(resp.isclosed())
        self.assertEqual(resp.read(2), 'xt')
        self.assertEqual(resp.read(1), '')
        self.assertTrue(resp.isclosed())

    def test_partial_reads_incomplete_body(self):
        # if the server shuts down the connection before the whole
        # content-length is delivered, the socket is gracefully closed
        body = "HTTP/1.1 200 Ok\r\nContent-Length: 10\r\n\r\nText"
        sock = FakeSocket(body)
        resp = httplib.HTTPResponse(sock)
        resp.begin()
        self.assertEqual(resp.read(2), 'Te')
        self.assertFalse(resp.isclosed())
        self.assertEqual(resp.read(2), 'xt')
        self.assertEqual(resp.read(1), '')
        self.assertTrue(resp.isclosed())

    def test_host_port(self):
        # Check invalid host_port

        # Note that httplib does not accept user:password@ in the host-port.
        for hp in ("www.python.org:abc", "user:password@www.python.org"):
            self.assertRaises(httplib.InvalidURL, httplib.HTTP, hp)

        for hp, h, p in (("[fe80::207:e9ff:fe9b]:8000", "fe80::207:e9ff:fe9b",
                          8000),
                         ("www.python.org:80", "www.python.org", 80),
                         ("www.python.org", "www.python.org", 80),
                         ("www.python.org:", "www.python.org", 80),
                         ("[fe80::207:e9ff:fe9b]", "fe80::207:e9ff:fe9b", 80)):
            http = httplib.HTTP(hp)
            c = http._conn
            if h != c.host:
                self.fail("Host incorrectly parsed: %s != %s" % (h, c.host))
            if p != c.port:
                self.fail("Port incorrectly parsed: %s != %s" % (p, c.host))

    def test_response_headers(self):
        # test response with multiple message headers with the same field name.
        text = ('HTTP/1.1 200 OK\r\n'
                'Set-Cookie: Customer="WILE_E_COYOTE";'
                ' Version="1"; Path="/acme"\r\n'
                'Set-Cookie: Part_Number="Rocket_Launcher_0001"; Version="1";'
                ' Path="/acme"\r\n'
                '\r\n'
                'No body\r\n')
        hdr = ('Customer="WILE_E_COYOTE"; Version="1"; Path="/acme"'
               ', '
               'Part_Number="Rocket_Launcher_0001"; Version="1"; Path="/acme"')
        s = FakeSocket(text)
        r = httplib.HTTPResponse(s)
        r.begin()
        cookies = r.getheader("Set-Cookie")
        if cookies != hdr:
            self.fail("multiple headers not combined properly")

    def test_read_head(self):
        # Test that the library doesn't attempt to read any data
        # from a HEAD request.  (Tickles SF bug #622042.)
        sock = FakeSocket(
            'HTTP/1.1 200 OK\r\n'
            'Content-Length: 14432\r\n'
            '\r\n',
            NoEOFStringIO)
        resp = httplib.HTTPResponse(sock, method="HEAD")
        resp.begin()
        if resp.read() != "":
            self.fail("Did not expect response from HEAD request")

    def test_send_file(self):
        expected = 'GET /foo HTTP/1.1\r\nHost: example.com\r\n' \
                   'Accept-Encoding: identity\r\nContent-Length:'

        body = open(__file__, 'rb')
        conn = httplib.HTTPConnection('example.com')
        sock = FakeSocket(body)
        conn.sock = sock
        conn.request('GET', '/foo', body)
        self.assertTrue(sock.data.startswith(expected))

    def test_send(self):
        expected = 'this is a test this is only a test'
        conn = httplib.HTTPConnection('example.com')
        sock = FakeSocket(None)
        conn.sock = sock
        conn.send(expected)
        self.assertEqual(expected, sock.data)
        sock.data = ''
        conn.send(array.array('c', expected))
        self.assertEqual(expected, sock.data)
        sock.data = ''
        conn.send(StringIO.StringIO(expected))
        self.assertEqual(expected, sock.data)

    def test_chunked(self):
        chunked_start = (
            'HTTP/1.1 200 OK\r\n'
            'Transfer-Encoding: chunked\r\n\r\n'
            'a\r\n'
            'hello worl\r\n'
            '1\r\n'
            'd\r\n'
        )
        sock = FakeSocket(chunked_start + '0\r\n')
        resp = httplib.HTTPResponse(sock, method="GET")
        resp.begin()
        self.assertEqual(resp.read(), 'hello world')
        resp.close()

        for x in ('', 'foo\r\n'):
            sock = FakeSocket(chunked_start + x)
            resp = httplib.HTTPResponse(sock, method="GET")
            resp.begin()
            try:
                resp.read()
            except httplib.IncompleteRead, i:
                self.assertEqual(i.partial, 'hello world')
                self.assertEqual(repr(i),'IncompleteRead(11 bytes read)')
                self.assertEqual(str(i),'IncompleteRead(11 bytes read)')
            else:
                self.fail('IncompleteRead expected')
            finally:
                resp.close()

    def test_chunked_head(self):
        chunked_start = (
            'HTTP/1.1 200 OK\r\n'
            'Transfer-Encoding: chunked\r\n\r\n'
            'a\r\n'
            'hello world\r\n'
            '1\r\n'
            'd\r\n'
        )
        sock = FakeSocket(chunked_start + '0\r\n')
        resp = httplib.HTTPResponse(sock, method="HEAD")
        resp.begin()
        self.assertEqual(resp.read(), '')
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.reason, 'OK')
        self.assertTrue(resp.isclosed())

    def test_negative_content_length(self):
        sock = FakeSocket('HTTP/1.1 200 OK\r\n'
                          'Content-Length: -1\r\n\r\nHello\r\n')
        resp = httplib.HTTPResponse(sock, method="GET")
        resp.begin()
        self.assertEqual(resp.read(), 'Hello\r\n')
        self.assertTrue(resp.isclosed())

    def test_incomplete_read(self):
        sock = FakeSocket('HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nHello\r\n')
        resp = httplib.HTTPResponse(sock, method="GET")
        resp.begin()
        try:
            resp.read()
        except httplib.IncompleteRead as i:
            self.assertEqual(i.partial, 'Hello\r\n')
            self.assertEqual(repr(i),
                             "IncompleteRead(7 bytes read, 3 more expected)")
            self.assertEqual(str(i),
                             "IncompleteRead(7 bytes read, 3 more expected)")
            self.assertTrue(resp.isclosed())
        else:
            self.fail('IncompleteRead expected')

    def test_epipe(self):
        sock = EPipeSocket(
            "HTTP/1.0 401 Authorization Required\r\n"
            "Content-type: text/html\r\n"
            "WWW-Authenticate: Basic realm=\"example\"\r\n",
            b"Content-Length")
        conn = httplib.HTTPConnection("example.com")
        conn.sock = sock
        self.assertRaises(socket.error,
                          lambda: conn.request("PUT", "/url", "body"))
        resp = conn.getresponse()
        self.assertEqual(401, resp.status)
        self.assertEqual("Basic realm=\"example\"",
                         resp.getheader("www-authenticate"))

    def test_filenoattr(self):
        # Just test the fileno attribute in the HTTPResponse Object.
        body = "HTTP/1.1 200 Ok\r\n\r\nText"
        sock = FakeSocket(body)
        resp = httplib.HTTPResponse(sock)
        self.assertTrue(hasattr(resp,'fileno'),
                'HTTPResponse should expose a fileno attribute')

    # Test lines overflowing the max line size (_MAXLINE in http.client)

    def test_overflowing_status_line(self):
        self.skipTest("disabled for HTTP 0.9 support")
        body = "HTTP/1.1 200 Ok" + "k" * 65536 + "\r\n"
        resp = httplib.HTTPResponse(FakeSocket(body))
        self.assertRaises((httplib.LineTooLong, httplib.BadStatusLine), resp.begin)

    def test_overflowing_header_line(self):
        body = (
            'HTTP/1.1 200 OK\r\n'
            'X-Foo: bar' + 'r' * 65536 + '\r\n\r\n'
        )
        resp = httplib.HTTPResponse(FakeSocket(body))
        self.assertRaises(httplib.LineTooLong, resp.begin)

    def test_overflowing_chunked_line(self):
        body = (
            'HTTP/1.1 200 OK\r\n'
            'Transfer-Encoding: chunked\r\n\r\n'
            + '0' * 65536 + 'a\r\n'
            'hello world\r\n'
            '0\r\n'
        )
        resp = httplib.HTTPResponse(FakeSocket(body))
        resp.begin()
        self.assertRaises(httplib.LineTooLong, resp.read)

    def test_early_eof(self):
        # Test httpresponse with no \r\n termination,
        body = "HTTP/1.1 200 Ok"
        sock = FakeSocket(body)
        resp = httplib.HTTPResponse(sock)
        resp.begin()
        self.assertEqual(resp.read(), '')
        self.assertTrue(resp.isclosed())

class OfflineTest(TestCase):
    def test_responses(self):
        self.assertEqual(httplib.responses[httplib.NOT_FOUND], "Not Found")


class SourceAddressTest(TestCase):
    def setUp(self):
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port = test_support.bind_port(self.serv)
        self.source_port = test_support.find_unused_port()
        self.serv.listen(5)
        self.conn = None

    def tearDown(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        self.serv.close()
        self.serv = None

    def testHTTPConnectionSourceAddress(self):
        self.conn = httplib.HTTPConnection(HOST, self.port,
                source_address=('', self.source_port))
        self.conn.connect()
        self.assertEqual(self.conn.sock.getsockname()[1], self.source_port)

    @unittest.skipIf(not hasattr(httplib, 'HTTPSConnection'),
                     'httplib.HTTPSConnection not defined')
    def testHTTPSConnectionSourceAddress(self):
        self.conn = httplib.HTTPSConnection(HOST, self.port,
                source_address=('', self.source_port))
        # We don't test anything here other the constructor not barfing as
        # this code doesn't deal with setting up an active running SSL server
        # for an ssl_wrapped connect() to actually return from.


class TimeoutTest(TestCase):
    PORT = None

    def setUp(self):
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        TimeoutTest.PORT = test_support.bind_port(self.serv)
        self.serv.listen(5)

    def tearDown(self):
        self.serv.close()
        self.serv = None

    def testTimeoutAttribute(self):
        '''This will prove that the timeout gets through
        HTTPConnection and into the socket.
        '''
        # default -- use global socket timeout
        self.assertIsNone(socket.getdefaulttimeout())
        socket.setdefaulttimeout(30)
        try:
            httpConn = httplib.HTTPConnection(HOST, TimeoutTest.PORT)
            httpConn.connect()
        finally:
            socket.setdefaulttimeout(None)
        self.assertEqual(httpConn.sock.gettimeout(), 30)
        httpConn.close()

        # no timeout -- do not use global socket default
        self.assertIsNone(socket.getdefaulttimeout())
        socket.setdefaulttimeout(30)
        try:
            httpConn = httplib.HTTPConnection(HOST, TimeoutTest.PORT,
                                              timeout=None)
            httpConn.connect()
        finally:
            socket.setdefaulttimeout(None)
        self.assertEqual(httpConn.sock.gettimeout(), None)
        httpConn.close()

        # a value
        httpConn = httplib.HTTPConnection(HOST, TimeoutTest.PORT, timeout=30)
        httpConn.connect()
        self.assertEqual(httpConn.sock.gettimeout(), 30)
        httpConn.close()


class HTTPSTimeoutTest(TestCase):
# XXX Here should be tests for HTTPS, there isn't any right now!

    def test_attributes(self):
        # simple test to check it's storing it
        if hasattr(httplib, 'HTTPSConnection'):
            h = httplib.HTTPSConnection(HOST, TimeoutTest.PORT, timeout=30)
            self.assertEqual(h.timeout, 30)

    @unittest.skipIf(not hasattr(httplib, 'HTTPS'), 'httplib.HTTPS not available')
    def test_host_port(self):
        # Check invalid host_port

        # Note that httplib does not accept user:password@ in the host-port.
        for hp in ("www.python.org:abc", "user:password@www.python.org"):
            self.assertRaises(httplib.InvalidURL, httplib.HTTP, hp)

        for hp, h, p in (("[fe80::207:e9ff:fe9b]:8000", "fe80::207:e9ff:fe9b",
                          8000),
                         ("pypi.python.org:443", "pypi.python.org", 443),
                         ("pypi.python.org", "pypi.python.org", 443),
                         ("pypi.python.org:", "pypi.python.org", 443),
                         ("[fe80::207:e9ff:fe9b]", "fe80::207:e9ff:fe9b", 443)):
            http = httplib.HTTPS(hp)
            c = http._conn
            if h != c.host:
                self.fail("Host incorrectly parsed: %s != %s" % (h, c.host))
            if p != c.port:
                self.fail("Port incorrectly parsed: %s != %s" % (p, c.host))


class TunnelTests(TestCase):
    def test_connect(self):
        response_text = (
            'HTTP/1.0 200 OK\r\n\r\n'   # Reply to CONNECT
            'HTTP/1.1 200 OK\r\n'       # Reply to HEAD
            'Content-Length: 42\r\n\r\n'
        )

        def create_connection(address, timeout=None, source_address=None):
            return FakeSocket(response_text, host=address[0], port=address[1])

        conn = httplib.HTTPConnection('proxy.com')
        conn._create_connection = create_connection

        # Once connected, we should not be able to tunnel anymore
        conn.connect()
        self.assertRaises(RuntimeError, conn.set_tunnel, 'destination.com')

        # But if close the connection, we are good.
        conn.close()
        conn.set_tunnel('destination.com')
        conn.request('HEAD', '/', '')

        self.assertEqual(conn.sock.host, 'proxy.com')
        self.assertEqual(conn.sock.port, 80)
        self.assertTrue('CONNECT destination.com' in conn.sock.data)
        self.assertTrue('Host: destination.com' in conn.sock.data)

        self.assertTrue('Host: proxy.com' not in conn.sock.data)

        conn.close()

        conn.request('PUT', '/', '')
        self.assertEqual(conn.sock.host, 'proxy.com')
        self.assertEqual(conn.sock.port, 80)
        self.assertTrue('CONNECT destination.com' in conn.sock.data)
        self.assertTrue('Host: destination.com' in conn.sock.data)


def test_main(verbose=None):
    test_support.run_unittest(HeaderTests, OfflineTest, BasicTest, TimeoutTest,
                              HTTPSTimeoutTest, SourceAddressTest, TunnelTests)

if __name__ == '__main__':
    test_main()
