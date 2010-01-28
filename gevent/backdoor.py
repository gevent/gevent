# @author Bob Ippolito
#
# Copyright (c) 2005-2006, Bob Ippolito
# Copyright (c) 2007, Linden Research, Inc.
# Copyright (c) 2008, Donovan Preston
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

try:
    sys.ps1
except AttributeError:
    sys.ps1 = '>>> '
try:
    sys.ps2
except AttributeError:
    sys.ps2 = '... '


class SocketConsole(Greenlet):

    def __init__(self, desc, locals):
        Greenlet.__init__(self)
        self.locals = locals
        # mangle the socket
        self.desc = desc
        readline = desc.readline
        self.old = {}
        self.fixups = {
            'softspace': 0,
            'isatty': lambda: True,
            'flush': lambda: None,
            'readline': lambda *a: readline(*a).replace('\r\n', '\n'),
        }
        for key, value in self.fixups.iteritems():
            if hasattr(desc, key):
                self.old[key] = getattr(desc, key)
            setattr(desc, key, value)

    def finalize(self):
        # restore the state of the socket
        for key in self.fixups:
            try:
                value = self.old[key]
            except KeyError:
                delattr(self.desc, key)
            else:
                setattr(self.desc, key, value)
        self.fixups.clear()
        self.old.clear()
        self.desc = None

    def switch(self, *args, **kw):
        self.saved = sys.stdin, sys.stderr, sys.stdout
        sys.stdin = sys.stdout = sys.stderr = self.desc
        Greenlet.switch(self, *args, **kw)

    def switch_out(self):
        sys.stdin, sys.stderr, sys.stdout = self.saved

    def _run(self):
        try:
            console = InteractiveConsole(self.locals)
            console.interact()
        finally:
            self.switch_out()
            self.finalize()


class BackdoorServer(Greenlet):

    def __init__(self, address, locals=None):
        Greenlet.__init__(self)
        if isinstance(address, socket.socket):
            self.socket = address
        else:
            self.socket = socket.tcp_listener(address)
        self.locals = locals

    def __str__(self):
        return '<BackdoorServer on %s>' % (self.socket, )

    def _run(self):
        while True:
            (conn, address) = self.socket.accept()
            print 'accepted connection from %s' % (address, )
            fileobj = _fileobject(conn)
            SocketConsole.spawn(fileobj, self.locals)


def backdoor_server(server, locals=None):
    import warnings
    warnings.warn("gevent.backdoor_server is deprecated; use BackdoorServer", DeprecationWarning, stacklevel=2)
    BackdoorServer.spawn(server, locals).join()


class _fileobject(socket._fileobject):

    def write(self, data):
        self._sock.sendall(data)


if __name__ == '__main__':
    if not sys.argv[1:]:
        print 'USAGE: %s PORT' % sys.argv[0]
    else:
        server = BackdoorServer.spawn(('127.0.0.1', int(sys.argv[1])))
        print server
        try:
            server.join()
        except KeyboardInterrupt:
            pass

