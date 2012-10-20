from gevent import monkey; monkey.patch_all()
import sys
import os
import array
import socket
import traceback
import time
import greentest
from functools import wraps

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

    def setUp(self):
        greentest.TestCase.setUp(self)
        listener = socket.socket()
        greentest.bind_and_listen(listener, ('127.0.0.1', 0))
        self.listener = listener
        self.port = listener.getsockname()[1]

    def cleanup(self):
        del self.listener

    def create_connection(self):
        sock = socket.socket()
        sock.connect(('127.0.0.1', self.port))
        return sock

    def _test_sendall(self, data):

        read_data = []

        def accept_and_read():
            try:
                read_data.append(self.listener.accept()[0].makefile().read())
            except:
                traceback.print_exc()
                os._exit(1)

        server = Thread(target=accept_and_read)
        client = self.create_connection()
        client.sendall(data)
        client.close()
        server.join()
        assert read_data[0] == self.long_data, read_data

    def test_sendall_str(self):
        self._test_sendall(self.long_data)

    def test_sendall_unicode(self):
        self._test_sendall(unicode(self.long_data))

    def test_sendall_array(self):
        data = array.array("B", self.long_data)
        self._test_sendall(data)

    def test_fullduplex(self):

        N = 100000

        def server():
            (client, addr) = self.listener.accept()
            # start reading, then, while reading, start writing. the reader should not hang forever

            def sendall():
                client.sendall('t' * N)

            sender = Thread(target=sendall)
            result = client.recv(1000)
            self.assertEqual(result, 'hello world')
            sender.join()

        server_thread = Thread(target=server)
        client = self.create_connection()
        client_reader = Thread(target=client.makefile().read, args=(N, ))
        time.sleep(0.1)
        client.send('hello world')
        time.sleep(0.1)

        # close() used to hang
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

    # On Windows send() accepts whatever is thrown at it
    if sys.platform != 'win32':

        def test_sendall_timeout(self):
            client_sock = []
            acceptor = Thread(target=lambda: client_sock.append(self.listener.accept()))
            client = self.create_connection()
            time.sleep(0.1)
            assert client_sock
            client.settimeout(0.1)
            data_sent = 'h' * 1000000
            start = time.time()
            self.assertRaises(self.TIMEOUT_ERROR, client.sendall, data_sent)
            took = time.time() - start
            assert 0.1 - 0.01 <= took <= 0.1 + 0.1, took
            acceptor.join()

    def test_makefile(self):

        def accept_once():
            conn, addr = self.listener.accept()
            fd = conn.makefile()
            fd.write('hello\n')
            fd.close()

        acceptor = Thread(target=accept_once)
        client = self.create_connection()
        fd = client.makefile()
        client.close()
        assert fd.readline() == 'hello\n'
        assert fd.read() == ''
        fd.close()
        acceptor.join()


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
        except socket.error:
            ex = sys.exc_info()[1]
            if 'refused' not in str(ex).lower():
                raise
        else:
            raise AssertionError('create_connection did not raise socket.error as expected')


if __name__ == '__main__':
    greentest.main()
