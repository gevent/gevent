# Copyright (c) 2009-2014, gevent contributors
# Based on eventlet.backdoor Copyright (c) 2005-2006, Bob Ippolito

from __future__ import print_function
import sys
from code import InteractiveConsole

from gevent import socket
from gevent.greenlet import Greenlet
from gevent.hub import PY3, getcurrent
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


class _Greenlet_stdreplace(Greenlet):
    _fileobj = None

    def switch(self, *args, **kw):
        if self._fileobj is not None:
            self.switch_in()
        Greenlet.switch(self, *args, **kw)

    def switch_in(self):
        self.saved = sys.stdin, sys.stderr, sys.stdout
        sys.stdin = sys.stdout = sys.stderr = self._fileobj

    def switch_out(self):
        sys.stdin, sys.stderr, sys.stdout = self.saved
        self.saved = None

    def run(self):
        try:
            return Greenlet.run(self)
        finally:
            # XXX why is this necessary?
            self.switch_out()


class BackdoorServer(StreamServer):

    def __init__(self, listener, locals=None, banner=None, **server_args):
        StreamServer.__init__(self, listener, spawn=_Greenlet_stdreplace.spawn, **server_args)
        self.locals = locals
        self.banner = banner
        self.stderr = sys.stderr

    def handle(self, conn, address):
        f = getcurrent()._fileobj = _fileobject(conn)
        f.stderr = self.stderr
        getcurrent().switch_in()
        try:
            console = InteractiveConsole(self.locals)
            # __builtins__ may either be the __builtin__ module or
            # __builtin__.__dict__ in the latter case typing
            # locals() at the backdoor prompt spews out lots of
            # useless stuff
            try:
                import __builtin__
            except ImportError:
                import builtins as __builtin__
            console.locals["__builtins__"] = __builtin__
            console.interact(banner=self.banner)
        except SystemExit as ex:  # raised by quit()
            if PY3:
                ex.__traceback__ = None
            else:
                sys.exc_clear()
        finally:
            conn.close()
            f.close()

    def do_close(self, socket, *args):
        pass


if PY3:
    import io

    class TTYRWPair(io.TextIOWrapper):
        def isatty(self, *args, **kwargs):
            return True

    def _fileobject(conn):
        return TTYRWPair(conn.makefile('rwb'), line_buffering=True)
else:
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
        print('USAGE: %s PORT' % sys.argv[0])
    else:
        BackdoorServer(('127.0.0.1', int(sys.argv[1])), locals={'hello': 'world'}).serve_forever()
