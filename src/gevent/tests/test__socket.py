# This line can be commented out so that most tests run with the
# system socket for comparison.
from gevent import monkey; monkey.patch_all()

import sys
import os
import array
import socket
import traceback
import time
import unittest
import gevent.testing as greentest
from functools import wraps

from gevent.testing import six
from gevent.testing import LARGE_TIMEOUT
from gevent.testing import support

# we use threading on purpose so that we can test both regular and gevent sockets with the same code
from threading import Thread as _Thread

errno_types = int

def wrap_error(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except: # pylint:disable=bare-except
            traceback.print_exc()
            os._exit(2)

    return wrapper


class Thread(_Thread):

    def __init__(self, **kwargs):
        target = kwargs.pop('target')
        target = wrap_error(target)
        _Thread.__init__(self, target=target, **kwargs)
        self.start()


class TestTCP(greentest.TestCase):

    __timeout__ = None
    TIMEOUT_ERROR = socket.timeout
    long_data = ", ".join([str(x) for x in range(20000)])
    if not isinstance(long_data, bytes):
        long_data = long_data.encode('ascii')

    def setUp(self):
        super(TestTCP, self).setUp()
        self.listener = self._close_on_teardown(self._setup_listener())

        # XXX: On Windows (at least with libev), if we have a cleanup/tearDown method
        # that does 'del self.listener' AND we haven't sometime
        # previously closed the listener (while the test body was executing)
        # we tend to sometimes see hangs when tests run in succession;
        # notably test_empty_send followed by test_makefile produces a hang
        # in test_makefile when it tries to read from the client_file, because
        # the accept() call in accept_once has not yet returned a new socket to
        # write to.

        # The cause *seems* to be that the listener socket in both tests gets the
        # same fileno(); or, at least, if we don't del the listener object,
        # we get a different fileno, and that scenario works.

        # Perhaps our logic is wrong in libev_vfd in the way we use
        # _open_osfhandle and determine we can close it?
        self.port = self.listener.getsockname()[1]

    def _setup_listener(self):
        listener = socket.socket()
        greentest.bind_and_listen(listener, ('127.0.0.1', 0))
        return listener

    def create_connection(self, host='127.0.0.1', port=None, timeout=None,
                          blocking=None):
        sock = socket.socket()
        sock.connect((host, port or self.port))
        if timeout is not None:
            sock.settimeout(timeout)
        if blocking is not None:
            sock.setblocking(blocking)
        return self._close_on_teardown(sock)

    def _test_sendall(self, data, match_data=None, client_method='sendall',
                      **client_args):

        read_data = []
        server_exc_info = []

        def accept_and_read():
            conn = None
            try:
                conn, _ = self.listener.accept()
                r = conn.makefile(mode='rb')
                read_data.append(r.read())
                r.flush()
                r.close()
            except: # pylint:disable=bare-except
                server_exc_info.append(sys.exc_info())
            finally:
                if conn:
                    conn.close()
                self.listener.close()

        server = Thread(target=accept_and_read)
        client = self.create_connection(**client_args)

        try:
            getattr(client, client_method)(data)
        finally:
            client.shutdown(socket.SHUT_RDWR)
            client.close()

        server.join()
        if match_data is None:
            match_data = self.long_data
        self.assertEqual(read_data[0], match_data)

        if server_exc_info:
            six.reraise(*server_exc_info[0])

    def test_sendall_str(self):
        self._test_sendall(self.long_data)

    if not six.PY3:
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
            (remote_client, _) = self.listener.accept()
            # start reading, then, while reading, start writing. the reader should not hang forever

            def sendall():
                remote_client.sendall(b't' * N)

            sender = Thread(target=sendall)
            result = remote_client.recv(1000)
            self.assertEqual(result, b'hello world')
            sender.join()
            remote_client.close()
            self.listener.close()

        server_thread = Thread(target=server)
        client = self.create_connection()
        client_file = client.makefile()
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
        client_sock = []
        acceptor = Thread(target=lambda: client_sock.append(self.listener.accept()))
        client = self.create_connection()
        client.settimeout(1)
        start = time.time()
        self.assertRaises(self.TIMEOUT_ERROR, client.recv, 1024)
        took = time.time() - start
        self.assertTimeWithinRange(took, 1 - 0.1, 1 + 0.1)
        acceptor.join()
        client.close()
        client_sock[0][0].close()

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
            self.listener.close()

        acceptor = Thread(target=accept_once)
        client = self.create_connection()
        # Closing the socket doesn't close the file
        client_file = client.makefile(mode='rb')
        client.close()
        line = client_file.readline()
        self.assertEqual(line, b'hello\n')
        self.assertEqual(client_file.read(), b'')
        client_file.close()
        acceptor.join()

    def test_makefile_timeout(self):

        def accept_once():
            conn, _ = self.listener.accept()
            try:
                time.sleep(0.3)
            finally:
                conn.close()  # for pypy

        acceptor = Thread(target=accept_once)
        client = self.create_connection()
        client.settimeout(0.1)
        fd = client.makefile(mode='rb')
        self.assertRaises(self.TIMEOUT_ERROR, fd.readline)
        client.close()
        fd.close()
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
        s.connect(('127.0.0.1', self.port))
        fd = s.makefile(mode='rb')
        self.assertEqual(fd.readline(), b'hello\n')

        fd.close()
        s.close()

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
                'refused|not known'
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
                raise E()

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
