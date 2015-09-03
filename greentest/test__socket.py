from gevent import monkey; monkey.patch_all()
import sys
import os
import array
import socket
import traceback
import time
import greentest
from functools import wraps
import six

# we use threading on purpose so that we can test both regular and gevent sockets with the same code
from threading import Thread as _Thread


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

    def create_connection(self):
        sock = socket.socket()
        sock.connect(('127.0.0.1', self.port))
        return sock

    def _test_sendall(self, data):

        read_data = []

        def accept_and_read():
            try:
                conn, _ = self.listener.accept()
                r = conn.makefile(mode='rb')
                read_data.append(r.read())
                r.close()
                conn.close()
            except:
                traceback.print_exc()
                os._exit(1)

        server = Thread(target=accept_and_read)
        client = self.create_connection()
        client.sendall(data)
        client.close()
        server.join()
        self.assertEqual(read_data[0], self.long_data)

    def test_sendall_str(self):
        self._test_sendall(self.long_data)

    if not six.PY3:
        def test_sendall_unicode(self):
            self._test_sendall(six.text_type(self.long_data))

    def test_sendall_array(self):
        data = array.array("B", self.long_data)
        self._test_sendall(data)

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
        assert 1 - 0.1 <= took <= 1 + 0.1, (time.time() - start)
        acceptor.join()
        client.close()
        client_sock[0][0].close()

    # On Windows send() accepts whatever is thrown at it
    if sys.platform != 'win32':

        def test_sendall_timeout(self):
            # Travis-CI container infrastructure is configured with
            # large socket buffers, at least 2MB, as-of Jun 3, 2015,
            # so we must be sure to send more data than that.
            data_sent = b'hello' * 1000000
            client_sock = []
            acceptor = Thread(target=lambda: client_sock.append(self.listener.accept()))
            client = self.create_connection()
            time.sleep(0.1)
            assert client_sock
            client.settimeout(0.1)
            start = time.time()
            try:
                self.assertRaises(self.TIMEOUT_ERROR, client.sendall, data_sent)
                took = time.time() - start
                assert 0.1 - 0.01 <= took <= 0.1 + 0.1, took
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
