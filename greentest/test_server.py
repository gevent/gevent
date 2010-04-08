#! /usr/bin/env python
#
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
import greentest
import gevent
from gevent import server, socket


class TestFatalErrors(greentest.TestCase):

    def setUp(self):
        greentest.TestCase.setUp(self)
        self.ss = server.StreamServer(("127.0.0.1", 0))
        self.ss.pre_start()
        self.socket = self.ss.socket
        self.ss.start()

    def _joinss(self):
        self.ss.join(0.1)
        try:
            self.assert_(self.ss.ready(), "server did not die")
        finally:
            self.ss.kill()

    def test_socket_shutdown(self):
        self.socket.shutdown(socket.SHUT_RDWR)
        self._joinss()

    def test_socket_close(self):
        os.close(self.socket.fileno())
        self._joinss()

    def test_socket_file(self):
        os.close(self.socket.fileno())
        f = open("/dev/zero", "r")
        self._joinss()
        del f


if __name__=='__main__':
    greentest.main()
