from __future__ import print_function
import greentest
from greentest import PY3
from gevent import socket
import gevent
from gevent.server import StreamServer
import errno
import os

# Timeouts very flaky on appveyor
_DEFAULT_SOCKET_TIMEOUT = 0.1 if not greentest.RUNNING_ON_APPVEYOR else 1.0
_DEFAULT_TEST_TIMEOUT = 5 if not greentest.RUNNING_ON_APPVEYOR else 10


class SimpleStreamServer(StreamServer):

    def handle(self, client_socket, address):
        fd = client_socket.makefile()
        try:
            request_line = fd.readline()
            if not request_line:
                return
            try:
                method, path, rest = request_line.split(' ', 3)
            except Exception:
                print('Failed to parse request line: %r' % (request_line, ))
                raise
            if path == '/ping':
                client_socket.sendall(b'HTTP/1.0 200 OK\r\n\r\nPONG')
            elif path in ['/long', '/short']:
                client_socket.sendall(b'hello')
                while True:
                    data = client_socket.recv(1)
                    if not data:
                        break
            else:
                client_socket.sendall(b'HTTP/1.0 404 WTF?\r\n\r\n')
        finally:
            fd.close()


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
        except socket.error as ex:
            if ex.args[0] != errno.ECONNRESET:
                raise

    @staticmethod
    def assertPoolFull(self):
        self.assertRaises(socket.timeout, self.assertRequestSucceeded, timeout=0.01)


class TestCase(greentest.TestCase):

    __timeout__ = _DEFAULT_TEST_TIMEOUT

    def cleanup(self):
        if getattr(self, 'server', None) is not None:
            self.server.stop()
            self.server = None

    def get_listener(self):
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        sock.listen(5)
        return sock

    def get_server_host_port_family(self):
        server_host = self.server.server_host
        if not server_host or server_host == '::':
            server_host = 'localhost'
        try:
            family = self.server.socket.family
        except AttributeError:
            # server deletes socket when closed
            family = socket.AF_INET

        return server_host, self.server.server_port, family

    def makefile(self, timeout=_DEFAULT_SOCKET_TIMEOUT, bufsize=1):
        server_host, server_port, family = self.get_server_host_port_family()

        sock = socket.socket(family=family)
        try:
            sock.connect((server_host, server_port))
        except Exception:
            # avoid ResourceWarning under Py3
            sock.close()
            raise

        if PY3:
            # Under Python3, you can't read and write to the same
            # makefile() opened in r, and r+ is not allowed
            kwargs = {'buffering': bufsize, 'mode': 'rwb'}
        else:
            kwargs = {'bufsize': bufsize}

        rconn = sock.makefile(**kwargs)
        if PY3:
            rconn._sock = sock
        rconn._sock.settimeout(timeout)
        sock.close()
        return rconn

    def send_request(self, url='/', timeout=_DEFAULT_SOCKET_TIMEOUT, bufsize=1):
        conn = self.makefile(timeout=timeout, bufsize=bufsize)
        conn.write(('GET %s HTTP/1.0\r\n\r\n' % url).encode('latin-1'))
        conn.flush()
        return conn

    def assertConnectionRefused(self):
        try:
            conn = self.makefile()
            try:
                raise AssertionError('Connection was not refused: %r' % (conn._sock, ))
            finally:
                conn.close()
        except socket.error as ex:
            if ex.args[0] not in (errno.ECONNREFUSED, errno.EADDRNOTAVAIL):
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
        conn.write(b'GET / HTTP/1.0\r\n\r\n')
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
        conn.close()

    def assertRequestSucceeded(self, timeout=_DEFAULT_SOCKET_TIMEOUT):
        conn = self.makefile(timeout=timeout)
        conn.write(b'GET /ping HTTP/1.0\r\n\r\n')
        result = conn.read()
        conn.close()
        assert result.endswith(b'\r\n\r\nPONG'), repr(result)

    def start_server(self):
        self.server.start()
        self.assertRequestSucceeded()
        self.assertRequestSucceeded()

    def stop_server(self):
        self.server.stop()
        self.assertConnectionRefused()

    def report_netstat(self, msg):
        return
        print(msg)
        os.system('sudo netstat -anp | grep %s' % os.getpid())
        print('^^^^^')

    def _create_server(self):
        return self.ServerSubClass(('', 0))

    def init_server(self):
        self.server = self._create_server()
        self.server.start()
        gevent.sleep(0.01)

    @property
    def socket(self):
        return self.server.socket

    def _test_invalid_callback(self):
        try:
            self.server = self.ServerClass(('', 0), lambda: None)
            self.server.start()

            self.expect_one_error()

            self.assert500()
            self.assert_error(TypeError)
        finally:
            self.server.stop()
            # XXX: There's something unreachable (with a traceback?)
            # We need to clear it to make the leak checks work on Travis;
            # so far I can't reproduce it locally on OS X.
            import gc; gc.collect()

    def ServerClass(self, *args, **kwargs):
        kwargs.setdefault('spawn', self.get_spawn())
        return Settings.ServerClass(*args, **kwargs)

    def ServerSubClass(self, *args, **kwargs):
        kwargs.setdefault('spawn', self.get_spawn())
        return Settings.ServerSubClass(*args, **kwargs)


class TestDefaultSpawn(TestCase):

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
        self.stop_server()
        self.report_netstat('after stop')

    def test_backlog_is_not_accepted_for_socket(self):
        self.switch_expected = False
        self.assertRaises(TypeError, self.ServerClass, self.get_listener(), backlog=25, handle=False)

    def test_backlog_is_accepted_for_address(self):
        self.server = self.ServerSubClass(('', 0), backlog=25)
        self.assertConnectionRefused()
        self._test_server_start_stop(restartable=False)

    def test_subclass_just_create(self):
        self.server = self.ServerSubClass(self.get_listener())
        self.assertNotAccepted()

    def test_subclass_with_socket(self):
        self.server = self.ServerSubClass(self.get_listener())
        # the connection won't be refused, because there exists a listening socket, but it won't be handled also
        self.assertNotAccepted()
        self._test_server_start_stop(restartable=True)

    def test_subclass_with_address(self):
        self.server = self.ServerSubClass(('', 0))
        self.assertConnectionRefused()
        self._test_server_start_stop(restartable=True)

    def test_invalid_callback(self):
        self._test_invalid_callback()

    def _test_serve_forever(self):
        g = gevent.spawn(self.server.serve_forever)
        try:
            gevent.sleep(0.01)
            self.assertRequestSucceeded()
            self.server.stop()
            assert not self.server.started
            self.assertConnectionRefused()
        finally:
            g.kill()
            g.get()

    def test_serve_forever(self):
        self.server = self.ServerSubClass(('127.0.0.1', 0))
        assert not self.server.started
        self.assertConnectionRefused()
        self._test_serve_forever()

    def test_serve_forever_after_start(self):
        self.server = self.ServerSubClass(('', 0))
        self.assertConnectionRefused()
        assert not self.server.started
        self.server.start()
        assert self.server.started
        self._test_serve_forever()

    def test_server_closes_client_sockets(self):
        self.server = self.ServerClass(('', 0), lambda *args: [])
        self.server.start()
        conn = self.send_request()
        timeout = gevent.Timeout.start_new(1)
        # use assert500 below?
        try:
            try:
                result = conn.read()
                if result:
                    assert result.startswith('HTTP/1.0 500 Internal Server Error'), repr(result)
            except socket.error as ex:
                if ex.args[0] == 10053:
                    pass  # "established connection was aborted by the software in your host machine"
                elif ex.args[0] == errno.ECONNRESET:
                    pass
                else:
                    raise
        finally:
            timeout.cancel()
            conn.close()
        self.stop_server()

    def init_server(self):
        self.server = self._create_server()
        self.server.start()
        gevent.sleep(0.01)

    @property
    def socket(self):
        return self.server.socket

    def test_error_in_spawn(self):
        self.init_server()
        assert self.server.started
        error = ExpectedError('test_error_in_spawn')
        self.server._spawn = lambda *args: gevent.getcurrent().throw(error)
        self.expect_one_error()
        self.assertAcceptedConnectionError()
        self.assert_error(ExpectedError, error)
        return
        if Settings.restartable:
            assert not self.server.started
        else:
            assert self.server.started
        gevent.sleep(0.1)
        assert self.server.started

    def test_server_repr_when_handle_is_instancemethod(self):
        # PR 501
        self.init_server()
        self.start_server()
        self.assertTrue('Server' in repr(self.server))

        self.server.set_handle(self.server.handle)
        self.assertTrue('handle=<bound method' in repr(self.server) and 'of self>' in repr(self.server),
                        repr(self.server))

        self.server.set_handle(self.test_server_repr_when_handle_is_instancemethod)
        self.assertTrue('test_server_repr_when_handle_is_instancemethod' in repr(self.server),
                        repr(self.server))

        def handle():
            pass
        self.server.set_handle(handle)
        self.assertTrue('handle=<function' in repr(self.server),
                        repr(self.server))


class TestRawSpawn(TestDefaultSpawn):

    def get_spawn(self):
        return gevent.spawn_raw


class TestPoolSpawn(TestDefaultSpawn):

    def get_spawn(self):
        return 2

    @greentest.skipOnAppVeyor("Connection timeouts are flaky")
    def test_pool_full(self):
        self.init_server()
        short_request = self.send_request('/short')
        long_request = self.send_request('/long')
        # keep long_request in scope, otherwise the connection will be closed
        gevent.sleep(0.01)
        self.assertPoolFull()
        self.assertPoolFull()
        # XXX Not entirely clear why this fails (timeout) on appveyor;
        # underlying socket timeout causing the long_request to close?
        self.assertPoolFull()
        short_request._sock.close()
        if PY3:
            # We use two makefiles to simulate reading/writing
            # under py3
            short_request.close()
        # gevent.http and gevent.wsgi cannot detect socket close, so sleep a little
        # to let /short request finish
        gevent.sleep(0.1)
        # XXX: This tends to timeout. Which is weird, because what would have
        # been the third call to assertPoolFull() DID NOT timeout, hence why it
        # was removed.
        self.assertRequestSucceeded()
        del long_request

    test_pool_full.error_fatal = False


class TestNoneSpawn(TestCase):

    def get_spawn(self):
        return None

    def test_invalid_callback(self):
        self._test_invalid_callback()

    def test_assertion_in_blocking_func(self):
        def sleep(*args):
            gevent.sleep(0)
        self.server = Settings.ServerClass(('', 0), sleep, spawn=None)
        self.server.start()
        self.expect_one_error()
        self.assert500()
        self.assert_error(AssertionError, 'Impossible to call blocking function in the event loop callback')


class ExpectedError(Exception):
    pass


if hasattr(socket, 'ssl'):

    class TestSSLSocketNotAllowed(TestCase):

        switch_expected = False

        def get_spawn(self):
            return gevent.spawn

        def test(self):
            from gevent.socket import ssl, socket
            listener = socket()
            listener.bind(('0.0.0.0', 0))
            listener.listen(5)
            listener = ssl(listener)
            self.assertRaises(TypeError, self.ServerSubClass, listener)

try:
    __import__('ssl')
except ImportError:
    pass
else:

    class TestSSLGetCertificate(TestCase):

        def _create_server(self):
            return self.ServerSubClass(('', 0),
                                       keyfile='server.key',
                                       certfile='server.crt')

        def get_spawn(self):
            return gevent.spawn

        def test_certificate(self):
            # Issue 801
            from gevent import monkey, ssl
            # only broken if *not* monkey patched
            self.assertFalse(monkey.is_module_patched('ssl'))
            self.assertFalse(monkey.is_module_patched('socket'))

            self.init_server()

            server_host, server_port, _family = self.get_server_host_port_family()
            ssl.get_server_certificate((server_host, server_port))

# test non-socket.error exception in accept call: fatal
# test error in spawn(): non-fatal
# test error in spawned handler: non-fatal


if __name__ == '__main__':
    greentest.main()
