from gevent import monkey; monkey.patch_all()
import sys
import os
import array
import socket
import traceback
import time
import greentest
from functools import wraps
import _six as six

# we use threading on purpose so that we can test both regular and gevent sockets with the same code
from threading import Thread as _Thread

errno_types = int

def wrap_error(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
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
    if six.PY3:
        long_data = long_data.encode('ascii')

    def setUp(self):
        greentest.TestCase.setUp(self)
        listener = socket.socket()
        greentest.bind_and_listen(listener, ('127.0.0.1', 0))
        self.listener = listener
        self.port = listener.getsockname()[1]

    def cleanup(self):
        if hasattr(self, 'listener'):
            try:
                self.listener.close()
            except:
                pass
            del self.listener

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
            try:
                conn, _ = self.listener.accept()
                r = conn.makefile(mode='rb')
                read_data.append(r.read())
                r.close()
                conn.close()
            except:
                server_exc_info.append(sys.exc_info())

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

    # On Windows send() accepts whatever is thrown at it
    if sys.platform != 'win32':

        _test_sendall_timeout_check_time = True
        # Travis-CI container infrastructure is configured with
        # large socket buffers, at least 2MB, as-of Jun 3, 2015,
        # so we must be sure to send more data than that.
        _test_sendall_data = b'hello' * 1000000

        def test_sendall_timeout(self):
            client_sock = []
            acceptor = Thread(target=lambda: client_sock.append(self.listener.accept()))
            client = self.create_connection()
            time.sleep(0.1)
            assert client_sock
            client.settimeout(0.1)
            start = time.time()
            try:
                self.assertRaises(self.TIMEOUT_ERROR, client.sendall, self._test_sendall_data)
                if self._test_sendall_timeout_check_time:
                    took = time.time() - start
                    assert 0.09 <= took <= 0.2, took
            finally:
                acceptor.join()
                client.close()
                client_sock[0][0].close()

    def test_makefile(self):

        def accept_once():
            conn, addr = self.listener.accept()
            fd = conn.makefile(mode='wb')
            fd.write(b'hello\n')
            fd.close()
            conn.close()  # for pypy

        acceptor = Thread(target=accept_once)
        client = self.create_connection()
        fd = client.makefile(mode='rb')
        client.close()
        assert fd.readline() == b'hello\n'
        assert fd.read() == b''
        fd.close()
        acceptor.join()

    def test_makefile_timeout(self):

        def accept_once():
            conn, addr = self.listener.accept()
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
            std_socket.setblocking(0)
            self.assertEqual(std_socket.type, s.type)

        s.close()

    def test_connect_ex_nonblocking_bad_connection(self):
        # Issue 841
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)
        ret = s.connect_ex(('localhost', get_port()))
        self.assertIsInstance(ret, errno_types)
        s.close()

    def test_connect_ex_gaierror(self):
        # Issue 841
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with self.assertRaises(socket.gaierror):
            s.connect_ex(('foo.bar.fizzbuzz', get_port()))
        s.close()

    def test_connect_ex_nonblocking_overflow(self):
        # Issue 841
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setblocking(False)
        with self.assertRaises(OverflowError):
            s.connect_ex(('localhost', 65539))
        s.close()

def get_port():
    tempsock = socket.socket()
    tempsock.bind(('', 0))
    port = tempsock.getsockname()[1]
    tempsock.close()
    return port


class TestCreateConnection(greentest.TestCase):

    __timeout__ = 5

    def test(self):
        try:
            socket.create_connection(('localhost', get_port()), timeout=30, source_address=('', get_port()))
        except socket.error as ex:
            if 'refused' not in str(ex).lower():
                raise
        else:
            raise AssertionError('create_connection did not raise socket.error as expected')


class TestFunctions(greentest.TestCase):

    def test_wait_timeout(self):
        # Issue #635
        import gevent.socket
        import gevent._socketcommon
        orig_get_hub = gevent.socket.get_hub

        class get_hub(object):
            def wait(self, io):
                gevent.sleep(10)

        class io(object):
            callback = None

        gevent._socketcommon.get_hub = get_hub
        try:
            try:
                gevent.socket.wait(io(), timeout=0.01)
            except gevent.socket.timeout:
                pass
            else:
                self.fail("Should raise timeout error")
        finally:
            gevent._socketcommon.get_hub = orig_get_hub

    # Creating new types in the function takes a cycle to cleanup.
    test_wait_timeout.ignore_leakcheck = True


if __name__ == '__main__':
    greentest.main()
