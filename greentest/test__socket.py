import os
import traceback
import gevent
from gevent import socket
import greentest
import time


class TestTCP(greentest.TestCase):

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.listener = socket.tcp_listener(('127.0.0.1', 0))
        self.tokill = []

    def tearDown(self):
        del self.listener
        try:
            gevent.killall(self.tokill, block=True)
        except:
            traceback.print_exc()
        # eat LinkedExited notifications
        while True:
            try:
                gevent.sleep(0.001)
                break
            except:
                traceback.print_exc()
        del self.tokill
        greentest.TestCase.tearDown(self)

    def create_connection(self):
        return socket.create_connection(('127.0.0.1', self.listener.getsockname()[1]))

    def test_fullduplex(self):

        def server():
            (client, addr) = self.listener.accept()
            # start reading, then, while reading, start writing. the reader should not hang forever
            N = 100000 # must be a big enough number so that sendall calls trampoline
            sender = gevent.spawn_link_exception(client.sendall, 't' * N)
            result = client.recv(1000)
            assert result == 'hello world', result
            sender.join(0.2)
            sender.kill(block=True)
            if client.__class__.__name__ == 'SSLObject':
                # if sslold.SSLObject is not closed then the other end will receive sslerror: (8, 'Unexpected EOF')
                # Not sure if it must be fixed but I don't want to waste time on that since
                # the preferred way to do ssl now is via gevent.ssl which works OK without explicit close
                client.close()

        #print '%s: client' % getcurrent()

        server_proc = gevent.spawn_link_exception(server)
        self.tokill.append(server_proc)
        client = self.create_connection()
        client_reader = gevent.spawn_link_exception(client.makefile().read)
        self.tokill.append(client_reader)
        gevent.sleep(0.001)
        client.send('hello world')

        # close() used to hang
        client.close()

        # this tests "full duplex" bug;
        server_proc.get()

        client_reader.get()

    def test_recv_timeout(self):
        acceptor = gevent.spawn_link_exception(self.listener.accept)
        client = self.create_connection()
        client.settimeout(0.1)
        start = time.time()
        try:
            data = client.recv(1024)
        except socket.timeout:
            assert 0.1 - 0.01 <= time.time() - start <= 0.1 + 0.1, (time.time() - start)
        else:
            raise AssertionError('socket.timeout should have been raised, instead recv returned %r' % (data, ))
        acceptor.get()

    def test_sendall_timeout(self):
        acceptor = gevent.spawn_link_exception(self.listener.accept)
        client = self.create_connection()
        client.settimeout(0.1)
        start = time.time()
        send_succeed = False
        data_sent = 'h' * 100000
        try:
            result = client.sendall(data_sent)
        except socket.timeout:
            assert 0.1 - 0.01 <= time.time() - start <= 0.1 + 0.1, (time.time() - start)
        else:
            assert time.time() - start <= 0.1 + 0.01, (time.time() - start)
            send_succeed = True
        conn, addr = acceptor.get()
        if send_succeed:
            client.close()
            data_read = conn.makefile().read()
            self.assertEqual(len(data_sent), len(data_read))
            self.assertEqual(data_sent, data_read)
            print 'WARNING: read the data instead of failing with timeout'

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


if hasattr(socket, 'ssl'):

    class TestSSL(TestTCP):

        certfile = os.path.join(os.path.dirname(__file__), 'test_server.crt')
        privfile = os.path.join(os.path.dirname(__file__), 'test_server.key')

        def setUp(self):
            TestTCP.setUp(self)
            self.listener = ssl_listener(('127.0.0.1', 0), self.privfile, self.certfile)

        def create_connection(self):
            return socket.ssl(socket.create_connection(('127.0.0.1', self.listener.getsockname()[1])))


    def ssl_listener(address, private_key, certificate):
        import _socket
        r = _socket.socket()
        sock = socket.ssl(r, private_key, certificate)
        socket.bind_and_listen(sock, address)
        return sock


if __name__=='__main__':
    greentest.main()
