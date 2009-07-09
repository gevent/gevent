# @author Donovan Preston
#
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

import os
import os.path
from greentest import TestCase, main

import gevent
from gevent import greenlet
from gevent import socket


class TestApi(TestCase):
    mode = 'static'

    certificate_file = os.path.join(os.path.dirname(__file__), 'test_server.crt')
    private_key_file = os.path.join(os.path.dirname(__file__), 'test_server.key')

    def test_tcp_listener(self):
        self.disable_switch_check()
        sock = socket.tcp_listener(('0.0.0.0', 0))
        assert sock.getsockname()[0] == '0.0.0.0'
        sock.close()

    def test_connect_tcp(self):
        def accept_once(listenfd):
            try:
                conn, addr = listenfd.accept()
                fd = conn.makeGreenFile()
                conn.close()
                fd.write('hello\n')
                fd.close()
            finally:
                listenfd.close()

        server = socket.tcp_listener(('0.0.0.0', 0))
        g = gevent.spawn(accept_once, server)
        try:
            client = socket.connect_tcp(('127.0.0.1', server.getsockname()[1]))
            fd = client.makeGreenFile()
            client.close()
            assert fd.readline() == 'hello\n'
            assert fd.read() == ''
            fd.close()
        finally:
            gevent.kill(g)

    def test_connect_ssl(self):
        def accept_once(listenfd):
            try:
                conn, addr = listenfd.accept()
                fl = conn.makeGreenFile('w')
                fl.write('hello\r\n')
                fl.close()
                conn.close()
            finally:
                listenfd.close()

        server = socket.ssl_listener(('0.0.0.0', 0),
                                  self.certificate_file,
                                  self.private_key_file)
        gevent.spawn(accept_once, server)

        client = socket.wrap_ssl(
            socket.connect_tcp(('127.0.0.1', server.getsockname()[1])))
        client = client.makeGreenFile()

        assert client.readline() == 'hello\r\n'
        assert client.read() == ''
        client.close()

    def test_server(self):
        connected = []
        server = socket.tcp_listener(('0.0.0.0', 0))
        bound_port = server.getsockname()[1]

        current = gevent.getcurrent()

        def accept_twice((conn, addr)):
            connected.append(True)
            conn.close()
            if len(connected) == 2:
                #server.close()
                # it's no longer possible with gevent to kill accept() loop by closing the listening socket
                # (the regular sockets also don't have this feature)
                # however, it's also not necessary, as it's as easy to kill it directly:
                gevent.kill(current, socket.error(32, 'broken pipe'))

        g1 = gevent.spawn(socket.connect_tcp, ('127.0.0.1', bound_port))
        g2 = gevent.spawn(socket.connect_tcp, ('127.0.0.1', bound_port))
        try:
            socket.tcp_server(server, accept_twice)
        finally:
            gevent.sleep(0)

        assert len(connected) == 2

    def test_001_trampoline_timeout(self):
        server = socket.tcp_listener(('0.0.0.0', 0))
        bound_port = server.getsockname()[1]

        try:
            desc = socket.GreenSocket()
            desc.connect(('127.0.0.1', bound_port))
            greenlet.wait_reader(desc.fileno(), timeout=0.1)
        except gevent.TimeoutError:
            pass # test passed
        else:
            assert False, "Didn't timeout"

    def test_timeout_cancel(self):
        server = socket.tcp_listener(('0.0.0.0', 0))
        bound_port = server.getsockname()[1]

        def client_connected((conn, addr)):
            conn.close()

        server_greenlet = gevent.getcurrent()

        def go():
            desc = socket.GreenSocket()
            desc.connect(('127.0.0.1', bound_port))
            try:
                greenlet.wait_reader(desc.fileno(), timeout=0.1)
            except gevent.TimeoutError:
                assert False, "Timed out"

            gevent.kill(server_greenlet, socket.error(32, 'broken error'))
            desc.close()

        g = gevent.spawn(go)
        try:
            try:
                socket.tcp_server(server, client_connected)
            except:
                gevent.kill(g)
                raise
        finally:
            gevent.sleep(0)

    def test_timeout_and_final_write(self):
        # This test verifies that a write on a socket that we've
        # stopped listening for doesn't result in an incorrect switch
        rpipe, wpipe = os.pipe()
        rfile = os.fdopen(rpipe,"r",0)
        wrap_rfile = socket.GreenPipe(rfile)
        wfile = os.fdopen(wpipe,"w",0)
        wrap_wfile = socket.GreenPipe(wfile)

        def sender(evt):
            gevent.sleep(0.02)
            wrap_wfile.write('hi')
            evt.send('sent via event')

        from gevent import coros
        evt = coros.event()
        gevent.spawn(sender, evt)
        try:
            # try and get some data off of this pipe
            # but bail before any is sent
            gevent.Timeout(0.01)
            _c = wrap_rfile.read(1)
            self.fail()
        except gevent.TimeoutError:
            pass

        result = evt.wait()
        self.assertEquals(result, 'sent via event')


if __name__ == '__main__':
    main()

