from __future__ import print_function
import os
from gevent import monkey; monkey.patch_all()
import re
import socket
import ssl
import threading
import unittest
import errno

dirname = os.path.dirname(os.path.abspath(__file__))
certfile = os.path.join(dirname, '2.7/keycert.pem')
pid = os.getpid()

import sys
PY3 = sys.version_info[0] >= 3
fd_types = int
if PY3:
    long = int
fd_types = (int, long)
WIN = sys.platform.startswith("win")

from greentest import get_open_files
try:
    import psutil
except ImportError:
    psutil = None


class Test(unittest.TestCase):

    extra_allowed_open_states = ()

    def tearDown(self):
        self.extra_allowed_open_states = ()
        unittest.TestCase.tearDown(self)

    def assert_raises_EBADF(self, func):
        try:
            result = func()
        except (socket.error, OSError) as ex:
            # Windows/Py3 raises "OSError: [WinError 10038]"
            if ex.args[0] == errno.EBADF:
                return
            if WIN and ex.args[0] == 10038:
                return
            raise
        raise AssertionError('NOT RAISED EBADF: %r() returned %r' % (func, result))

    def assert_fd_open(self, fileno):
        assert isinstance(fileno, fd_types)
        open_files = get_open_files()
        if fileno not in open_files:
            raise AssertionError('%r is not open:\n%s' % (fileno, open_files['data']))

    def assert_fd_closed(self, fileno):
        assert isinstance(fileno, fd_types), repr(fileno)
        assert fileno > 0, fileno
        open_files = get_open_files()
        if fileno in open_files:
            raise AssertionError('%r is not closed:\n%s' % (fileno, open_files['data']))

    def _assert_sock_open(self, sock):
        # requires the psutil output
        open_files = get_open_files()
        sockname = sock.getsockname()
        for x in open_files['data']:
            if getattr(x, 'laddr', None) == sockname:
                assert x.status in (psutil.CONN_LISTEN, psutil.CONN_ESTABLISHED) + self.extra_allowed_open_states, x.status
                return
        raise AssertionError("%r is not open:\n%s" % (sock, open_files['data']))

    def assert_open(self, sock, *rest):
        if isinstance(sock, fd_types):
            if not WIN:
                self.assert_fd_open(sock)
        else:
            fileno = sock.fileno()
            assert isinstance(fileno, fd_types), fileno
            sockname = sock.getsockname()
            assert isinstance(sockname, tuple), sockname
            if not WIN:
                self.assert_fd_open(fileno)
            else:
                self._assert_sock_open(sock)
        if rest:
            self.assert_open(rest[0], *rest[1:])

    def assert_closed(self, sock, *rest):
        if isinstance(sock, fd_types):
            self.assert_fd_closed(sock)
        else:
            # Under Python3, the socket module returns -1 for a fileno
            # of a closed socket; under Py2 it raises
            if PY3:
                self.assertEqual(sock.fileno(), -1)
            else:
                self.assert_raises_EBADF(sock.fileno)
            self.assert_raises_EBADF(sock.getsockname)
            self.assert_raises_EBADF(sock.accept)
        if rest:
            self.assert_closed(rest[0], *rest[1:])

    def make_open_socket(self):
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        if WIN:
            # Windows doesn't show as open until this
            s.listen(1)
        self.assert_open(s, s.fileno())
        return s


class TestSocket(Test):

    def test_simple_close(self):
        s = self.make_open_socket()
        fileno = s.fileno()
        s.close()
        self.assert_closed(s, fileno)

    def test_makefile1(self):
        s = self.make_open_socket()
        fileno = s.fileno()
        f = s.makefile()
        self.assert_open(s, fileno)
        s.close()
        # Under python 2, this closes socket wrapper object but not the file descriptor;
        # under python 3, both stay open
        if PY3:
            self.assert_open(s, fileno)
        else:
            self.assert_closed(s)
            self.assert_open(fileno)
        f.close()
        self.assert_closed(s)
        self.assert_closed(fileno)

    def test_makefile2(self):
        s = self.make_open_socket()
        fileno = s.fileno()
        self.assert_open(s, fileno)
        f = s.makefile()
        self.assert_open(s)
        self.assert_open(s, fileno)
        f.close()
        # closing fileobject does not close the socket
        self.assert_open(s, fileno)
        s.close()
        self.assert_closed(s, fileno)

    def test_server_simple(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            fileno = client_socket.fileno()
            self.assert_open(client_socket, fileno)
            client_socket.close()
            self.assert_closed(client_socket)
        finally:
            t.join()
            listener.close()

    def test_server_makefile1(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            fileno = client_socket.fileno()
            f = client_socket.makefile()
            self.assert_open(client_socket, fileno)
            client_socket.close()
            # Under python 2, this closes socket wrapper object but not the file descriptor;
            # under python 3, both stay open
            if PY3:
                self.assert_open(client_socket, fileno)
            else:
                self.assert_closed(client_socket)
                self.assert_open(fileno)
            f.close()
            self.assert_closed(client_socket, fileno)
        finally:
            t.join()
            listener.close()

    def test_server_makefile2(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            fileno = client_socket.fileno()
            f = client_socket.makefile()
            self.assert_open(client_socket, fileno)
            # closing fileobject does not close the socket
            f.close()
            self.assert_open(client_socket, fileno)
            client_socket.close()
            self.assert_closed(client_socket, fileno)
        finally:
            t.join()
            listener.close()


class TestSSL(Test):

    def test_simple_close(self):
        s = self.make_open_socket()
        fileno = s.fileno()
        s = ssl.wrap_socket(s)
        fileno = s.fileno()
        self.assert_open(s, fileno)
        s.close()
        self.assert_closed(s, fileno)

    def test_makefile1(self):
        s = self.make_open_socket()
        fileno = s.fileno()

        s = ssl.wrap_socket(s)
        fileno = s.fileno()
        self.assert_open(s, fileno)
        f = s.makefile()
        self.assert_open(s, fileno)
        s.close()
        self.assert_open(s, fileno)
        f.close()
        self.assert_closed(s, fileno)

    def test_makefile2(self):
        s = self.make_open_socket()
        fileno = s.fileno()

        s = ssl.wrap_socket(s)
        fileno = s.fileno()
        self.assert_open(s, fileno)
        f = s.makefile()
        self.assert_open(s, fileno)
        f.close()
        # closing fileobject does not close the socket
        self.assert_open(s, fileno)
        s.close()
        self.assert_closed(s, fileno)

    def test_server_simple(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))
            ssl.wrap_socket(connector)

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            client_socket = ssl.wrap_socket(client_socket, keyfile=certfile, certfile=certfile, server_side=True)
            fileno = client_socket.fileno()
            self.assert_open(client_socket, fileno)
            client_socket.close()
            self.assert_closed(client_socket, fileno)
        finally:
            t.join()
            listener.close()

    def test_server_makefile1(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))
            ssl.wrap_socket(connector)

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            client_socket = ssl.wrap_socket(client_socket, keyfile=certfile, certfile=certfile, server_side=True)
            fileno = client_socket.fileno()
            self.assert_open(client_socket, fileno)
            f = client_socket.makefile()
            self.assert_open(client_socket, fileno)
            client_socket.close()
            self.assert_open(client_socket, fileno)
            f.close()
            self.assert_closed(client_socket, fileno)
        finally:
            t.join()
            connector.close()

    def test_server_makefile2(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))
            ssl.wrap_socket(connector)

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            client_socket = ssl.wrap_socket(client_socket, keyfile=certfile, certfile=certfile, server_side=True)
            fileno = client_socket.fileno()
            self.assert_open(client_socket, fileno)
            f = client_socket.makefile()
            self.assert_open(client_socket, fileno)
            # Closing fileobject does not close SSLObject
            f.close()
            self.assert_open(client_socket, fileno)
            client_socket.close()
            self.assert_closed(client_socket, fileno)
        finally:
            t.join()
            listener.close()
            connector.close()

    def test_serverssl_makefile1(self):
        listener = socket.socket()
        fileno = listener.fileno()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)
        listener = ssl.wrap_socket(listener, keyfile=certfile, certfile=certfile)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))
            ssl.wrap_socket(connector)

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            fileno = client_socket.fileno()
            self.assert_open(client_socket, fileno)
            f = client_socket.makefile()
            self.assert_open(client_socket, fileno)
            client_socket.close()
            self.assert_open(client_socket, fileno)
            f.close()
            self.assert_closed(client_socket, fileno)
        finally:
            t.join()
            listener.close()
            connector.close()

    def test_serverssl_makefile2(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        listener.listen(1)
        listener = ssl.wrap_socket(listener, keyfile=certfile, certfile=certfile)

        connector = socket.socket()

        def connect():
            connector.connect(('127.0.0.1', port))
            s = ssl.wrap_socket(connector)
            s.sendall(b'test_serverssl_makefile2')
            s.close()
            connector.close()

        t = threading.Thread(target=connect)
        t.start()

        try:
            client_socket, _addr = listener.accept()
            fileno = client_socket.fileno()
            self.assert_open(client_socket, fileno)
            f = client_socket.makefile()
            self.assert_open(client_socket, fileno)
            self.assertEqual(f.read(), 'test_serverssl_makefile2')
            self.assertEqual(f.read(), '')
            f.close()
            if WIN and psutil:
                # Hmm?
                self.extra_allowed_open_states = (psutil.CONN_CLOSE_WAIT,)
            self.assert_open(client_socket, fileno)
            client_socket.close()
            self.assert_closed(client_socket, fileno)
        finally:
            t.join()
            listener.close()


if __name__ == '__main__':
    unittest.main()
