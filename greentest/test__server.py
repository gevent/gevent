import greentest
from gevent import socket
import gevent
from gevent.server import StreamServer
import errno
import os


class SimpleStreamServer(StreamServer):

    def handle(self, client_socket, address):
        fd = client_socket.makefile()
        request_line = fd.readline()
        if not request_line:
            return
        try:
            method, path, rest = request_line.split(' ', 3)
        except Exception:
            print 'Failed to parse request line: %r' % (request_line, )
            raise
        if path == '/ping':
            client_socket.sendall('HTTP/1.0 200 OK\r\n\r\nPONG')
        elif path in ['/long', '/short']:
            client_socket.sendall('hello')
            while True:
                data = client_socket.recv(1)
                if not data:
                    break
        else:
            client_socket.sendall('HTTP/1.0 404 WTF?\r\n\r\n')


class Settings:
    ServerClass = StreamServer
    ServerSubClass = SimpleStreamServer
    restartable = True
    close_socket_detected = True

    @staticmethod
    def assertAcceptedConnectionError(self):
        conn = self.makefile()
        result = conn.read()
        assert not result, repr(result)

    assert500 = assertAcceptedConnectionError

    @staticmethod
    def assert503(self):
        # regular reads timeout
        self.assert500()
        # attempt to send anything reset the connection
        try:
            self.send_request()
        except socket.error, ex:
            if ex[0] != errno.ECONNRESET:
                raise

    @staticmethod
    def assertPoolFull(self):
        self.assertRaises(socket.timeout, self.assertRequestSucceeded, timeout=0.01)


class TestCase(greentest.TestCase):

    __timeout__ = 10

    def cleanup(self):
        if getattr(self, 'server', None) is not None:
            self.server.stop()
            self.server = None

    def get_listener(self):
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        sock.listen(5)
        return sock

    def makefile(self, timeout=0.1, bufsize=1):
        sock = socket.create_connection((self.server.server_host, self.server.server_port))
        fobj = sock.makefile(bufsize=bufsize)
        fobj._sock.settimeout(timeout)
        return fobj

    def send_request(self, url='/', timeout=0.1, bufsize=1):
        conn = self.makefile(timeout=timeout, bufsize=bufsize)
        conn.write('GET %s HTTP/1.0\r\n\r\n' % url)
        conn.flush()
        return conn

    def assertConnectionRefused(self):
        try:
            conn = self.makefile()
            raise AssertionError('Connection was not refused: %r' % (conn._sock, ))
        except socket.error, ex:
            if ex[0] not in (errno.ECONNREFUSED, errno.EADDRNOTAVAIL):
                raise

    def assert500(self):
        Settings.assert500(self)

    def assert503(self):
        Settings.assert503(self)

    def assertAcceptedConnectionError(self):
        Settings.assertAcceptedConnectionError(self)

    def assertPoolFull(self):
        Settings.assertPoolFull(self)

    def assertNotAccepted(self):
        conn = self.makefile()
        conn.write('GET / HTTP/1.0\r\n\r\n')
        conn.flush()
        result = ''
        try:
            while True:
                data = conn._sock.recv(1)
                if not data:
                    break
                result += data
        except socket.timeout:
            assert not result, repr(result)
            return
        assert result.startswith('HTTP/1.0 500 Internal Server Error'), repr(result)

    def assertRequestSucceeded(self, timeout=0.1):
        conn = self.makefile(timeout=timeout)
        conn.write('GET /ping HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result.endswith('\r\n\r\nPONG'), repr(result)

    def start_server(self):
        self.server.start()
        self.assertRequestSucceeded()
        self.assertRequestSucceeded()

    def stop_server(self):
        self.server.stop()
        self.assertConnectionRefused()

    def report_netstat(self, msg):
        return
        print msg
        os.system('sudo netstat -anp | grep %s' % os.getpid())
        print '^^^^^'

    def init_server(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.server.start()
        gevent.sleep(0.01)

    @property
    def socket(self):
        return self.server.socket

    def _test_invalid_callback(self):
        try:
            self.hook_stderr()
            self.server = self.ServerClass(('127.0.0.1', 0), lambda: None)
            self.server.start()
            self.assert500()
            self.assert_stderr_traceback('TypeError')
            self.assert_stderr(self.invalid_callback_message)
        finally:
            self.server.stop()

    def ServerClass(self, *args, **kwargs):
        kwargs.setdefault('spawn', self.get_spawn())
        return Settings.ServerClass(*args, **kwargs)

    def ServerSubClass(self, *args, **kwargs):
        kwargs.setdefault('spawn', self.get_spawn())
        return Settings.ServerSubClass(*args, **kwargs)


class TestDefaultSpawn(TestCase):

    invalid_callback_message = '<Greenlet failed with TypeError'

    def get_spawn(self):
        return gevent.spawn

    def _test_server_start_stop(self, restartable):
        self.report_netstat('before start')
        self.start_server()
        self.report_netstat('after start')
        if restartable and Settings.restartable:
            self.server.stop_accepting()
            self.report_netstat('after stop_accepting')
            self.assertNotAccepted()
            self.server.start_accepting()
            self.report_netstat('after start_accepting')
            self.assertRequestSucceeded()
        else:
            self.assertRaises(Exception, self.server.start)  # XXX which exception exactly?
        self.stop_server()
        self.report_netstat('after stop')

    def test_backlog_is_not_accepted_for_socket(self):
        self.switch_expected = False
        self.assertRaises(TypeError, self.ServerClass, self.get_listener(), backlog=25)

    def test_backlog_is_accepted_for_address(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0), backlog=25)
        self.assertConnectionRefused()
        self._test_server_start_stop(restartable=False)

    def test_subclass_just_create(self):
        self.server = self.ServerSubClass(self.get_listener())
        self.assertNotAccepted()

    def test_subclass_with_socket(self):
        self.server = self.ServerSubClass(self.get_listener())
        # the connection won't be refused, because there exists a listening socket, but it won't be handled also
        self.assertNotAccepted()
        self.server.reuse_addr = 1
        self._test_server_start_stop(restartable=True)

    def test_subclass_with_address(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.assertConnectionRefused()
        self._test_server_start_stop(restartable=True)

    def test_invalid_callback(self):
        self._test_invalid_callback()

    def _test_serve_forever(self):
        g = gevent.spawn_link_exception(self.server.serve_forever)
        try:
            gevent.sleep(0.01)
            self.assertRequestSucceeded()
            self.server.stop()
            assert not self.server.started
            self.assertConnectionRefused()
        finally:
            g.kill()

    def test_serve_forever(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        assert not self.server.started
        self.assertConnectionRefused()
        self._test_serve_forever()

    def test_serve_forever_after_start(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.assertConnectionRefused()
        assert not self.server.started
        self.server.start()
        assert self.server.started
        self._test_serve_forever()

    def test_server_closes_client_sockets(self):
        self.server = self.ServerClass(('127.0.0.1', 0), lambda *args: [])
        self.server.start()
        conn = self.send_request()
        timeout = gevent.Timeout.start_new(1)
        # use assert500 below?
        try:
            try:
                result = conn.read()
                if result:
                    assert result.startswith('HTTP/1.0 500 Internal Server Error'), repr(result)
            except socket.error, ex:
                if ex[0] != errno.ECONNRESET:
                    raise
        finally:
            timeout.cancel()
        self.stop_server()

    def init_server(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        self.server.start()
        gevent.sleep(0.01)

    @property
    def socket(self):
        return self.server.socket

    def test_error_in_spawn(self):
        self.init_server()
        assert self.server.started
        self.hook_stderr()
        error = ExpectedError('test_error_in_spawn')
        self.server._spawn = lambda *args: gevent.getcurrent().throw(error)
        self.assertAcceptedConnectionError()
        self.assert_stderr_traceback(error)
        #self.assert_stderr('^WARNING: <SimpleStreamServer .*?>: ignoring test_error_in_spawn \\(sleeping \d.\d+ seconds\\)\n$')
        self.assert_stderr('<.*?>: Failed to handle...')
        return
        if Settings.restartable:
            assert not self.server.started
        else:
            assert self.server.started
        gevent.sleep(0.1)
        assert self.server.started


class TestRawSpawn(TestDefaultSpawn):

    invalid_callback_message = 'Failed active_event...'

    def get_spawn(self):
        return gevent.spawn_raw


class TestPoolSpawn(TestDefaultSpawn):

    def get_spawn(self):
        return 2

    def test_pool_full(self):
        self.init_server()
        short_request = self.send_request('/short')
        long_request = self.send_request('/long')
        # keep long_request in scope, otherwise the connection will be closed
        gevent.sleep(0.01)
        self.assertPoolFull()
        self.assertPoolFull()
        self.assertPoolFull()
        short_request._sock.close()
        # gevent.http and gevent.wsgi cannot detect socket close, so sleep a little
        # to let /short request finish
        gevent.sleep(0.1)
        self.assertRequestSucceeded()


class TestNoneSpawn(TestCase):

    invalid_callback_message = '<.*?>: Failed to handle'

    def get_spawn(self):
        return None

    def test_invalid_callback(self):
        self._test_invalid_callback()

    def test_assertion_in_blocking_func(self):
        def sleep(*args):
            gevent.sleep(0)
        self.server = Settings.ServerClass(('127.0.0.1', 0), sleep, spawn=None)
        self.server.start()
        self.hook_stderr()
        self.assert500()
        self.assert_mainloop_assertion(self.invalid_callback_message)


class ExpectedError(Exception):
    pass


class TestSSLSocketNotAllowed(TestCase):

    switch_expected = False

    def get_spawn(self):
        return gevent.spawn

    if hasattr(socket, 'ssl'):

        def test(self):
            from gevent.socket import ssl, socket
            listener = socket()
            listener.bind(('0.0.0.0', 0))
            listener.listen(5)
            listener = ssl(listener)
            self.assertRaises(TypeError, self.ServerSubClass, listener)

# test non-socket.error exception in accept call: fatal
# test error in spawn(): non-fatal
# test error in spawned handler: non-fatal


if __name__ == '__main__':
    greentest.main()
