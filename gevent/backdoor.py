# @author Bob Ippolito
#
# Copyright (c) 2005-2006, Bob Ippolito
# Copyright (c) 2007, Linden Research, Inc.
# Copyright (c) 2008, Donovan Preston
# Copyright (c) 2009-2010, Denis Bilenko
# Copyright (c) 2011, gevent contributors
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

import sys
from code import InteractiveConsole

from gevent import socket
from gevent.greenlet import Greenlet
from gevent.server import StreamServer

__all__ = ['BackdoorServer']

try:
    sys.ps1
except AttributeError:
    sys.ps1 = '>>> '
try:
    sys.ps2
except AttributeError:
    sys.ps2 = '... '


class SocketConsole(Greenlet):

    def __init__(self, locals, conn, banner=None):
        Greenlet.__init__(self)
        self.locals = locals
        self.desc = _fileobject(conn)
        self.banner = banner

    def finalize(self):
        self.desc = None

    def switch(self, *args, **kw):
        self.saved = sys.stdin, sys.stderr, sys.stdout
        sys.stdin = sys.stdout = sys.stderr = self.desc
        Greenlet.switch(self, *args, **kw)

    def switch_out(self):
        sys.stdin, sys.stderr, sys.stdout = self.saved

    def _run(self):
        try:
            try:
                console = InteractiveConsole(self.locals)
                # __builtins__ may either be the __builtin__ module or
                # __builtin__.__dict__ in the latter case typing
                # locals() at the backdoor prompt spews out lots of
                # useless stuff
                import __builtin__
                console.locals["__builtins__"] = __builtin__
                console.interact(banner=self.banner)
            except SystemExit:  # raised by quit()
                sys.exc_clear()
        finally:
            self.switch_out()
            self.finalize()


class BackdoorServer(StreamServer):
    """Provide a backdoor to a program for debugging purposes.

    You may bind to any interface, but for security purposes it is recommended
    that you bind to 127.0.0.1.

    Basic usage:

    >> from gevent.backdoor import BackdoorServer
    >> server = BackdoorServer(('127.0.0.1', 5001),
    ...                         locals={'foo': "From defined scope!"})
    >> server.serve_forever()

    In a another terminal, connect with...

    $ telnet 127.0.0.1 5001
    Trying 127.0.0.1...
    Connected to 127.0.0.1.
    Escape character is '^]'.
    Python 2.7.5 (default, May 12 2013, 12:00:47)
    [GCC 4.8.0 20130502 (prerelease)] on linux2
    Type "help", "copyright", "credits" or "license" for more information.
    (InteractiveConsole)
    >> print foo
    From defined scope!
    """

    def __init__(self, listener, locals=None, banner=None, **server_args):
        StreamServer.__init__(self, listener, spawn=None, **server_args)
        self.locals = locals
        self.banner = banner
        # QQQ passing pool instance as 'spawn' is not possible; should it be fixed?

    def handle(self, conn, address):
        SocketConsole.spawn(self.locals, conn, banner=self.banner)


class _fileobject(socket._fileobject):

    def write(self, data):
        self._sock.sendall(data)

    def isatty(self):
        return True

    def flush(self):
        pass

    def readline(self, *a):
        return socket._fileobject.readline(self, *a).replace("\r\n", "\n")


if __name__ == '__main__':
    if not sys.argv[1:]:
        print ('USAGE: %s PORT' % sys.argv[0])
    else:
        BackdoorServer(('127.0.0.1', int(sys.argv[1]))).serve_forever()
