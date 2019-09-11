# This line can be commented out so that most tests run with the
# system socket for comparison.
from __future__ import print_function
from __future__ import absolute_import

from gevent import monkey; monkey.patch_all()

import sys
import array
import socket
import time
import unittest
from functools import wraps

from gevent._compat import reraise

import gevent.testing as greentest

from gevent.testing import six
from gevent.testing import LARGE_TIMEOUT
from gevent.testing import support
from gevent.testing import params
from gevent.testing.sockets import tcp_listener
from gevent.testing.skipping import skipWithoutExternalNetwork

# we use threading on purpose so that we can test both regular and
# gevent sockets with the same code
from threading import Thread as _Thread
from threading import Event

errno_types = int


class Thread(_Thread):

    def __init__(self, **kwargs):
        target = kwargs.pop('target')
        self.terminal_exc = None
        @wraps(target)
        def errors_are_fatal(*args, **kwargs):
            try:
                return target(*args, **kwargs)
            except: # pylint:disable=bare-except
                self.terminal_exc = sys.exc_info()
                raise

        _Thread.__init__(self, target=errors_are_fatal, **kwargs)
        self.start()


class TestTCP(greentest.TestCase):

    __timeout__ = None
    TIMEOUT_ERROR = socket.timeout
    long_data = ", ".join([str(x) for x in range(20000)])
    if not isinstance(long_data, bytes):
        long_data = long_data.encode('ascii')

    def setUp(self):
        super(TestTCP, self).setUp()
        if '-v' in sys.argv:
            printed = []
            try:
                from time import perf_counter as now
            except ImportError:
                from time import time as now
            def log(*args):
                if not printed:
                    print()
                    printed.append(1)
                print("\t ->", now(), *args)

            orig_cot = self._close_on_teardown
            def cot(o):
                log("Registering for teardown", o)
                def c():
                    log("Closing on teardown", o)
                    o.close()
                orig_cot(c)
                return o
            self._close_on_teardown = cot

        else:
            def log(*_args):
                "Does nothing"
        self.log = log


        self.listener = self._close_on_teardown(self._setup_listener())
        # It is important to watch the lifetimes of socket objects and
        # ensure that:
        # (1) they are closed; and
        # (2) *before* the next test begins.
        #
        # For example, it's a bad bad thing to leave a greenlet running past the
        # scope of the individual test method if that greenlet will close
        # a socket object --- especially if that socket object might also have been
        # closed explicitly.
        #
        # On Windows, we've seen issue with filenos getting reused while something
        # still thinks they have the original fileno around. When they later
        # close that fileno, a completely unrelated object is closed.
        self.port = self.listener.getsockname()[1]

    def _setup_listener(self):
        return tcp_listener()

    def create_connection(self, host=None, port=None, timeout=None,
                          blocking=None):
        sock = self._close_on_teardown(socket.socket())
        sock.connect((host or params.DEFAULT_CONNECT, port or self.port))
        if timeout is not None:
            sock.settimeout(timeout)
        if blocking is not None:
            sock.setblocking(blocking)
        return sock

    def _test_sendall(self, data, match_data=None, client_method='sendall',
                      **client_args):
        # pylint:disable=too-many-locals,too-many-branches,too-many-statements
        log = self.log
        log("Sendall", client_method)

        read_data = []
        accepted_event = Event()

        def accept_and_read():
            log("accepting", self.listener)
            conn, _ = self.listener.accept()
            try:
                r = conn.makefile(mode='rb')
                try:
                    log("accepted on server", conn)
                    accepted_event.set()
                    log("reading")
                    read_data.append(r.read())
                    log("done reading")
                finally:
                    r.close()
                    del r
            finally:
                conn.close()
                del conn


        server = Thread(target=accept_and_read)
        try:
            log("creating client connection")
            client = self.create_connection(**client_args)

            # We seem to have a buffer stuck somewhere on appveyor?
            # https://ci.appveyor.com/project/denik/gevent/builds/27320824/job/bdbax88sqnjoti6i#L712
            should_unwrap = hasattr(client, 'unwrap') and greentest.PY37 and greentest.WIN

            # The implicit reference-based nastiness of Python 2
            # sockets interferes, especially when using SSL sockets.
            # The best way to get a decent FIN to the server is to shutdown
            # the output. Doing that on Python 3, OTOH, is contraindicated.
            should_shutdown = greentest.PY2

            # It's important to wait for the server to fully accept before
            # we shutdown and close the socket. In SSL mode, the number
            # and timing of data exchanges to complete the handshake and
            # thus exactly when greenlet switches occur, varies by TLS version.
            #
            # It turns out that on < TLS1.3, we were getting lucky and the
            # server was the greenlet that raced ahead and blocked in r.read()
            # before the client returned from create_connection().
            #
            # But when TLS 1.3 was deployed (OpenSSL 1.1), the *client* was the
            # one that raced ahead while the server had yet to return from
            # self.listener.accept(). So the client sent the data to the socket,
            # and closed, before the server could do anything, and the server,
            # when it got switched to by server.join(), found its new socket
            # dead.
            accepted_event.wait()
            log("accepted", client)
            try:
                getattr(client, client_method)(data)
            except:
                import traceback; traceback.print_exc()
                # unwrapping might not work after this because we're in
                # a bad state.
                if should_unwrap:
                    client.shutdown(socket.SHUT_RDWR)
                    should_unwrap = False
                    should_shutdown = False
                raise
            finally:
                log("shutdown")
                if should_shutdown:
                    client.shutdown(socket.SHUT_RDWR)
                elif should_unwrap:
                    try:
                        client.unwrap()
                    except OSError as e:
                        if greentest.PY37 and greentest.WIN and e.errno == 0:
                            # ? 3.7.4 on AppVeyor sometimes raises
                            # "OSError[errno 0] Error" here, which doesn't make
                            # any sense.
                            pass
                        else:
                            raise
                log("closing")
                client.close()
        finally:
            server.join(4)
            assert not server.is_alive()

        if server.terminal_exc:
            reraise(*server.terminal_exc)

        if match_data is None:
            match_data = self.long_data
        self.assertEqual(read_data, [match_data])

    def test_sendall_str(self):
        self._test_sendall(self.long_data)

    if six.PY2:
        def test_sendall_unicode(self):
            self._test_sendall(six.text_type(self.long_data))

    def test_sendall_array(self):
        data = array.array("B", self.long_data)
        self._test_sendall(data)

    def test_sendall_empty(self):
        data = b''
        self._test_sendall(data, data)

    def test_sendall_empty_with_timeout(self):
        # Issue 719
        data = b''
        self._test_sendall(data, data, timeout=10)

    def test_sendall_nonblocking(self):
        # https://github.com/benoitc/gunicorn/issues/1282
        # Even if the socket is non-blocking, we make at least
        # one attempt to send data. Under Py2 before this fix, we
        # would incorrectly immediately raise a timeout error
        data = b'hi\n'
        self._test_sendall(data, data, blocking=False)

    def test_empty_send(self):
        # Issue 719
        data = b''
        self._test_sendall(data, data, client_method='send')

    def test_fullduplex(self):
        N = 100000

        def server():
            remote_client, _ = self.listener.accept()
            self._close_on_teardown(remote_client)
            # start reading, then, while reading, start writing. the reader should not hang forever

            sender = Thread(target=remote_client.sendall,
                            args=((b't' * N),))
            try:
                result = remote_client.recv(1000)
                self.assertEqual(result, b'hello world')
            finally:
                sender.join()

        server_thread = Thread(target=server)
        client = self.create_connection()
        client_file = self._close_on_teardown(client.makefile())
        client_reader = Thread(target=client_file.read, args=(N, ))
        time.sleep(0.1)
        client.sendall(b'hello world')
        time.sleep(0.1)

        # close() used to hang
        client_file.close()
        client.close()

        # this tests "full duplex" bug;
        server_thread.join()

        client_reader.join()

    def test_recv_timeout(self):
        def accept():
            # make sure the conn object stays alive until the end;
            # premature closing triggers a ResourceWarning and
            # EOF on the client.
            conn, _ = self.listener.accept()
            self._close_on_teardown(conn)

        acceptor = Thread(target=accept)
        client = self.create_connection()
        try:
            client.settimeout(1)
            start = time.time()
            with self.assertRaises(self.TIMEOUT_ERROR):
                client.recv(1024)
            took = time.time() - start
            self.assertTimeWithinRange(took, 1 - 0.1, 1 + 0.1)
        finally:
            acceptor.join()

    # Subclasses can disable  this
    _test_sendall_timeout_check_time = True

    # Travis-CI container infrastructure is configured with
    # large socket buffers, at least 2MB, as-of Jun 3, 2015,
    # so we must be sure to send more data than that.
    # In 2018, this needs to be increased *again* as a smaller value was
    # still often being sent.
    _test_sendall_data = b'hello' * 100000000

    # This doesn't make much sense...why are we really skipping this?
    @greentest.skipOnWindows("On Windows send() accepts whatever is thrown at it")
    def test_sendall_timeout(self):
        client_sock = []
        acceptor = Thread(target=lambda: client_sock.append(self.listener.accept()))
        client = self.create_connection()
        time.sleep(0.1)
        assert client_sock
        client.settimeout(0.1)
        start = time.time()
        try:
            with self.assertRaises(self.TIMEOUT_ERROR):
                client.sendall(self._test_sendall_data)
            if self._test_sendall_timeout_check_time:
                took = time.time() - start
                self.assertTimeWithinRange(took, 0.09, 0.2)
        finally:
            acceptor.join()
            client.close()
            client_sock[0][0].close()

    def test_makefile(self):
        def accept_once():
            conn, _ = self.listener.accept()
            fd = conn.makefile(mode='wb')
            fd.write(b'hello\n')
            fd.flush()
            fd.close()
            conn.close()  # for pypy

        acceptor = Thread(target=accept_once)
        try:
            client = self.create_connection()
            # Closing the socket doesn't close the file
            client_file = client.makefile(mode='rb')
            client.close()
            line = client_file.readline()
            self.assertEqual(line, b'hello\n')
            self.assertEqual(client_file.read(), b'')
            client_file.close()
        finally:
            acceptor.join()

    def test_makefile_timeout(self):

        def accept_once():
            conn, _ = self.listener.accept()
            try:
                time.sleep(0.3)
            finally:
                conn.close()  # for pypy

        acceptor = Thread(target=accept_once)
        try:
            client = self.create_connection()
            client.settimeout(0.1)
            fd = client.makefile(mode='rb')
            self.assertRaises(self.TIMEOUT_ERROR, fd.readline)
            client.close()
            fd.close()
        finally:
            acceptor.join()

    def test_attributes(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
        self.assertEqual(socket.AF_INET, s.type)
        self.assertEqual(socket.SOCK_DGRAM, s.family)
        self.assertEqual(0, s.proto)

        if hasattr(socket, 'SOCK_NONBLOCK'):
            s.settimeout(1)
            self.assertEqual(socket.AF_INET, s.type)

            s.setblocking(0)
            std_socket = monkey.get_original('socket', 'socket')(socket.AF_INET, socket.SOCK_DGRAM, 0)
            try:
                std_socket.setblocking(0)
                self.assertEqual(std_socket.type, s.type)
            finally:
                std_socket.close()

        s.close()

    def test_connect_ex_nonblocking_bad_connection(self):
        # Issue 841
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setblocking(False)
            ret = s.connect_ex((greentest.DEFAULT_LOCAL_HOST_ADDR, support.find_unused_port()))
            self.assertIsInstance(ret, errno_types)
        finally:
            s.close()

    @skipWithoutExternalNetwork("Tries to resolve hostname")
    def test_connect_ex_gaierror(self):
        # Issue 841
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.assertRaises(socket.gaierror):
                s.connect_ex(('foo.bar.fizzbuzz', support.find_unused_port()))
        finally:
            s.close()

    def test_connect_ex_nonblocking_overflow(self):
        # Issue 841
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.setblocking(False)
            with self.assertRaises(OverflowError):
                s.connect_ex((greentest.DEFAULT_LOCAL_HOST_ADDR, 65539))
        finally:
            s.close()

    @unittest.skipUnless(hasattr(socket, 'SOCK_CLOEXEC'),
                         "Requires SOCK_CLOEXEC")
    def test_connect_with_type_flags_ignored(self):
        # Issue 944
        # If we have SOCK_CLOEXEC or similar, we shouldn't be passing
        # them through to the getaddrinfo call that connect() makes
        SOCK_CLOEXEC = socket.SOCK_CLOEXEC # pylint:disable=no-member
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM | SOCK_CLOEXEC)

        def accept_once():
            conn, _ = self.listener.accept()
            fd = conn.makefile(mode='wb')
            fd.write(b'hello\n')
            fd.close()
            conn.close()

        acceptor = Thread(target=accept_once)
        try:
            s.connect((params.DEFAULT_CONNECT, self.port))
            fd = s.makefile(mode='rb')
            self.assertEqual(fd.readline(), b'hello\n')

            fd.close()
            s.close()
        finally:
            acceptor.join()


class TestCreateConnection(greentest.TestCase):

    __timeout__ = LARGE_TIMEOUT

    def test_refuses(self, **conn_args):
        connect_port = support.find_unused_port()
        with self.assertRaisesRegex(
                socket.error,
                # We really expect "connection refused". It's unclear
                # where/why we would get '[errno -2] name or service not known'
                # but it seems some systems generate that.
                # https://github.com/gevent/gevent/issues/1389
                # Somehow extremly rarely we've also seen 'address already in use',
                # which makes even less sense.
                'refused|not known|already in use'
        ):
            socket.create_connection(
                (greentest.DEFAULT_BIND_ADDR, connect_port),
                timeout=30,
                **conn_args
            )

    def test_refuses_from_port(self):
        source_port = support.find_unused_port()
        # Usually we don't want to bind/connect to '', but
        # using it as the source is required if we don't want to hang,
        # at least on some systems (OS X)
        self.test_refuses(source_address=('', source_port))


    @greentest.ignores_leakcheck
    @skipWithoutExternalNetwork("Tries to resolve hostname")
    def test_base_exception(self):
        # such as a GreenletExit or a gevent.timeout.Timeout

        class E(BaseException):
            pass

        class MockSocket(object):

            created = ()
            closed = False

            def __init__(self, *_):
                MockSocket.created += (self,)

            def connect(self, _):
                raise E(_)

            def close(self):
                self.closed = True

        def mockgetaddrinfo(*_):
            return [(1, 2, 3, 3, 5),]

        import gevent.socket as gsocket
        # Make sure we're monkey patched
        self.assertEqual(gsocket.create_connection, socket.create_connection)
        orig_socket = gsocket.socket
        orig_getaddrinfo = gsocket.getaddrinfo

        try:
            gsocket.socket = MockSocket
            gsocket.getaddrinfo = mockgetaddrinfo

            with self.assertRaises(E):
                socket.create_connection(('host', 'port'))

            self.assertEqual(1, len(MockSocket.created))
            self.assertTrue(MockSocket.created[0].closed)

        finally:
            MockSocket.created = ()
            gsocket.socket = orig_socket
            gsocket.getaddrinfo = orig_getaddrinfo

class TestFunctions(greentest.TestCase):

    @greentest.ignores_leakcheck
    # Creating new types in the function takes a cycle to cleanup.
    def test_wait_timeout(self):
        # Issue #635
        import gevent.socket
        import gevent._socketcommon

        class io(object):
            callback = None

            def start(self, *_args):
                gevent.sleep(10)

        with self.assertRaises(gevent.socket.timeout):
            gevent.socket.wait(io(), timeout=0.01) # pylint:disable=no-member


    def test_signatures(self):
        # https://github.com/gevent/gevent/issues/960
        exclude = []
        if greentest.PYPY:
            # Up through at least PyPy 5.7.1, they define these as
            # gethostbyname(host), whereas the official CPython argument name
            # is hostname. But cpython doesn't allow calling with keyword args.
            # Likewise for gethostbyaddr: PyPy uses host, cpython uses ip_address
            exclude.append('gethostbyname')
            exclude.append('gethostbyname_ex')
            exclude.append('gethostbyaddr')
        self.assertMonkeyPatchedFuncSignatures('socket', exclude=exclude)


class TestSocket(greentest.TestCase):

    def test_shutdown_when_closed(self):
        # https://github.com/gevent/gevent/issues/1089
        # we once raised an AttributeError.
        s = socket.socket()
        s.close()
        with self.assertRaises(socket.error):
            s.shutdown(socket.SHUT_RDWR)

if __name__ == '__main__':
    greentest.main()
