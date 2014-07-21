# Copyright (c) 2006-2007, Linden Research, Inc.
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from greentest import TestCase, main, tcp_listener
import gevent
from gevent import socket
from gevent.hub import PY3
import sys


PYPY = hasattr(sys, 'pypy_version_info')


class TestGreenIo(TestCase):

    def test_close_with_makefile(self):

        def accept_close_early(listener):
            # verify that the makefile and the socket are truly independent
            # by closing the socket prior to using the made file
            try:
                conn, addr = listener.accept()
                fd = conn.makefile('rw')
                conn.close()
                fd.write('hello\n')
                fd.close()
                if PY3:
                    self.assertRaises(ValueError, fd.write, 'a')
                    self.assertRaises(ValueError, fd.flush)
                else:
                    r = fd.write('a')
                    assert r is None, r
                    self.assertRaises(AttributeError, fd.flush)
                self.assertRaises(socket.error, conn.send, b'b')
            finally:
                listener.close()

        def accept_close_late(listener):
            # verify that the makefile and the socket are truly independent
            # by closing the made file and then sending a character
            try:
                conn, addr = listener.accept()
                fd = conn.makefile('rw')
                fd.write('hello')
                fd.close()
                conn.send(b'\n')
                conn.close()
                if PY3:
                    self.assertRaises(ValueError, fd.write, 'a')
                    self.assertRaises(ValueError, fd.flush)
                else:
                    r = fd.write('a')
                    assert r is None, r
                    self.assertRaises(AttributeError, fd.flush)
                self.assertRaises(socket.error, conn.send, b'b')
            finally:
                listener.close()

        def did_it_work(server):
            client = socket.create_connection(('127.0.0.1', server.getsockname()[1]))
            fd = client.makefile()
            client.close()
            assert fd.readline() == 'hello\n'
            assert fd.read() == ''
            fd.close()

        server = tcp_listener(('0.0.0.0', 0))
        server_greenlet = gevent.spawn(accept_close_early, server)
        did_it_work(server)
        server_greenlet.kill()

        server = tcp_listener(('0.0.0.0', 0))
        server_greenlet = gevent.spawn(accept_close_late, server)
        did_it_work(server)
        server_greenlet.kill()

    def test_del_closes_socket(self):
        if PYPY:
            return
        timer = gevent.Timeout.start_new(0.5)

        def accept_once(listener):
            # delete/overwrite the original conn
            # object, only keeping the file object around
            # closing the file object should close everything
            # update: this is not true for PY3
            try:
                sock, addr = listener.accept()
                conn = sock.makefile('rw')
                conn.write('hello\n')
                sock.close()
                conn.close()
                if PY3:
                    self.assertRaises(ValueError, conn.write, 'a')
                    self.assertRaises(ValueError, conn.flush)
                else:
                    r = conn.write('a')
                    assert r is None, r
                    self.assertRaises(AttributeError, conn.flush)
            finally:
                listener.close()

        server = tcp_listener(('0.0.0.0', 0))
        gevent.spawn(accept_once, server)
        client = socket.create_connection(('127.0.0.1', server.getsockname()[1]))
        fd = client.makefile()
        client.close()
        assert fd.read() == 'hello\n'
        assert fd.read() == ''

        timer.cancel()

if __name__ == '__main__':
    main()
