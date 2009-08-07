import os
import gevent
from gevent import socket, coros
import greentest
import time

class TestTCP(greentest.TestCase):

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.listener = socket.tcp_listener(('127.0.0.1', 0))

    def tearDown(self):
        del self.listener
        greentest.TestCase.tearDown(self)

    def create_connection(self):
        return socket.create_connection(('127.0.0.1', self.listener.getsockname()[1]))

    def test_fullduplex(self):

        def server():
            (client, addr) = self.listener.accept()
            # start reading, then, while reading, start writing. the reader should not hang forever
            N = 100000 # must be a big enough number so that sendall calls trampoline
            gevent.spawn_link_exception(client.sendall, 't' * N)
            result = client.recv(1000)
            assert result == 'hello world', result

        #print '%s: client' % getcurrent()

        server_proc = gevent.spawn_link_exception(server)
        client = self.create_connection()
        client_reader = gevent.spawn_link_exception(client.makefile().read)
        gevent.sleep(0.001)
        client.send('hello world')

        # close() used to hang
        client.close()

        # this tests "full duplex" bug;
        server_proc.get()

        client_reader.get()

    def test_recv_timeout(self):
        client = self.create_connection()
        client.settimeout(0.1)
        start = time.time()
        try:
            data = client.recv(1024)
        except socket.timeout:
            assert time.time() - start >= 0.1 - 0.001, (time.time() - start)
        else:
            raise AssertionError('socket.timeout should have been raised, instead recv returned %r' % (data, ))

    def test_sendall_timeout(self):
        client = self.create_connection()
        client.settimeout(0.01)
        start = time.time()
        try:
            result = client.sendall('h'*100000)
        except socket.timeout:
            assert time.time() - start >= 0.01, (time.time() - start)
        else:
            raise AssertionError('socket.timeout should have been raised, instead sendall returned %r' % (result, ))

    def test_makefile(self):
        def accept_once():
            conn, addr = self.listener.accept()
            fd = conn.makefile()
            conn.close()
            fd.write('hello\n')
            fd.close()

        acceptor = gevent.spawn(accept_once)
        client = self.create_connection()
        fd = client.makefile()
        client.close()
        assert fd.readline() == 'hello\n'
        assert fd.read() == ''
        fd.close()
        acceptor.get()

    # this test was copied from api_test.py
    # using kill() like that is not good, so tcp_server should return an object
    # that provides kill() method or removed altogether
    def test_server(self):
        connected = []

        current = gevent.getcurrent()

        def accept_twice((conn, addr)):
            connected.append(True)
            conn.close()
            if len(connected) == 2:
                #gevent.kill(current, socket.error(32, 'broken pipe'))
                gevent.core.active_event(current.throw, socket.error(32, 'broken pipe'))

        g1 = gevent.spawn_link_exception(self.create_connection)
        g2 = gevent.spawn_link_exception(self.create_connection)
        socket.tcp_server(self.listener, accept_twice)
        assert len(connected) == 2
        gevent.joinall([g1, g2])


class TestSSL(TestTCP):

    certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
    privfile = os.path.join(os.path.dirname(__file__), 'test_server.key')

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.listener = socket.ssl_listener(('127.0.0.1', 0), self.privfile, self.certfile)

    def tearDown(self):
        del self.listener
        greentest.TestCase.tearDown(self)

    def create_connection(self):
        return socket.create_connection_ssl(('127.0.0.1', self.listener.getsockname()[1]))

    def test_recv_timeout(self):
        incoming = coros.Queue() # preventing the incoming socket from being GCed before the test finished
        acceptor = gevent.spawn_link_exception(lambda : incoming.send(self.listener.accept()))
        client = self.create_connection()
        client.settimeout(0.1)
        start = time.time()
        try:
            data = client.recv(1024)
        except socket.timeout:
            assert time.time() - start >= 0.1, (time.time() - start)
        else:
            raise AssertionError('socket.timeout should have been raised, instead recv returned %r' % (data, ))
        acceptor.get()

    def test_sendall_timeout(self):
        incoming = coros.Queue() # preventing the incoming socket from being GCed before the test finished
        acceptor = gevent.spawn_link_exception(lambda : incoming.send(self.listener.accept()))
        client = self.create_connection()
        client.settimeout(0.1)
        start = time.time()
        try:
            result = client.sendall('h'*1000000)
        except socket.timeout:
            assert time.time() - start >= 0.1, (time.time() - start)
        else:
            raise AssertionError('socket.timeout should have been raised, instead sendall returned %r' % (result, ))
        acceptor.get()


if __name__=='__main__':
    greentest.main()
