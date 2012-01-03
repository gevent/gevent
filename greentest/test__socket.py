import os
import sys
import array
import gevent
from gevent import socket
import greentest
import time


class TestTCP(greentest.TestCase):

    TIMEOUT_ERROR = socket.timeout
    long_data = ", ".join([str(x) for x in range(20000)])

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.listener = greentest.tcp_listener(('127.0.0.1', 0))

    def tearDown(self):
        del self.listener
        greentest.TestCase.tearDown(self)

    def create_connection(self):
        return socket.create_connection(('127.0.0.1', self.listener.getsockname()[1]))

    def sendall(self, data):
        def accept_and_read():
            conn, addr = self.listener.accept()
            fd = conn.makefile()
            conn.close()
            read = fd.read()
            fd.close()
            return read

        server = gevent.spawn(accept_and_read)
        try:
            client = self.create_connection()
            client.sendall(data)
            client.close()
            read = server.get()
            assert read == self.long_data
        finally:
            server.kill()

    def test_sendall_str(self):
        self.sendall(self.long_data)

    def test_sendall_unicode(self):
        self.sendall(unicode(self.long_data))

    def test_sendall_array(self):
        data = array.array("B", self.long_data)
        self.sendall(data)

    def test_fullduplex(self):

        def server():
            (client, addr) = self.listener.accept()
            # start reading, then, while reading, start writing. the reader should not hang forever
            N = 100000  # must be a big enough number so that sendall calls trampoline
            sender = gevent.spawn(client.sendall, 't' * N)
            result = client.recv(1000)
            assert result == 'hello world', result
            sender.join(timeout=0.2)
            sender.kill()
            sender.get()

        #print '%s: client' % getcurrent()

        server_proc = gevent.spawn(server)
        client = self.create_connection()
        client_reader = gevent.spawn(client.makefile().read)
        gevent.sleep(0.001)
        client.send('hello world')

        # close() used to hang
        client.close()

        # this tests "full duplex" bug;
        server_proc.get()

        client_reader.get()

    def test_recv_timeout(self):
        acceptor = gevent.spawn(self.listener.accept)
        try:
            client = self.create_connection()
            client.settimeout(0.1)
            start = time.time()
            try:
                data = client.recv(1024)
            except self.TIMEOUT_ERROR:
                assert 0.1 - 0.01 <= time.time() - start <= 0.1 + 0.1, (time.time() - start)
            else:
                raise AssertionError('%s should have been raised, instead recv returned %r' % (self.TIMEOUT_ERROR, data, ))
        finally:
            acceptor.get()

    def test_sendall_timeout(self):
        acceptor = gevent.spawn(self.listener.accept)
        try:
            client = self.create_connection()
            client.settimeout(0.1)
            start = time.time()
            send_succeed = False
            data_sent = 'h' * 100000
            try:
                client.sendall(data_sent)
            except self.TIMEOUT_ERROR:
                assert 0.1 - 0.01 <= time.time() - start <= 0.1 + 0.1, (time.time() - start)
            else:
                assert time.time() - start <= 0.1 + 0.01, (time.time() - start)
                send_succeed = True
        finally:
            conn, addr = acceptor.get()
        if send_succeed:
            client.close()
            data_read = conn.makefile().read()
            self.assertEqual(len(data_sent), len(data_read))
            self.assertEqual(data_sent, data_read)
            print '%s: WARNING: read the data instead of failing with timeout' % self.__class__.__name__

    def test_makefile(self):
        def accept_once():
            conn, addr = self.listener.accept()
            fd = conn.makefile()
            conn.close()
            fd.write('hello\n')
            fd.close()

        acceptor = gevent.spawn(accept_once)
        try:
            client = self.create_connection()
            fd = client.makefile()
            client.close()
            assert fd.readline() == 'hello\n'
            assert fd.read() == ''
            fd.close()
        finally:
            acceptor.get()


if hasattr(socket, 'ssl'):

    class TestSSL(TestTCP):

        certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
        privfile = os.path.join(os.path.dirname(__file__), 'test_server.key')
        TIMEOUT_ERROR = socket.sslerror

        def setUp(self):
            TestTCP.setUp(self)
            self.listener = ssl_listener(('127.0.0.1', 0), self.privfile, self.certfile)

        def create_connection(self):
            return socket.ssl(socket.create_connection(('127.0.0.1', self.listener.getsockname()[1])))

    def ssl_listener(address, private_key, certificate):
        import _socket
        r = _socket.socket()
        sock = socket.ssl(r, private_key, certificate)
        greentest.bind_and_listen(sock, address)
        return sock


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


class TestClosedSocket(greentest.TestCase):

    switch_expected = False

    def test(self):
        sock = socket.socket()
        sock.close()
        try:
            sock.send('a', timeout=1)
        except socket.error, ex:
            if ex.errno != 9:
                raise


if __name__ == '__main__':
    greentest.main()
