# Copyright (c) 2009-2014, gevent contributors
# Based on eventlet.backdoor Copyright (c) 2005-2006, Bob Ippolito

from __future__ import print_function
import sys
from code import InteractiveConsole

from gevent import socket
from gevent.greenlet import Greenlet
from gevent.hub import PY3, PYPY, getcurrent
from gevent.server import StreamServer
if PYPY:
    import gc

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
                console.locals["__builtins__"] = __builtin__
            except ImportError:
                import builtins
                console.locals["builtins"] = builtins
                console.locals['__builtins__'] = builtins
            console.interact(banner=self.banner)
        except SystemExit:  # raised by quit()
            if not PY3:
                sys.exc_clear()
        finally:
            conn.close()
            f.close()
            if PYPY:
                # The underlying socket somewhere has a reference
                # that's not getting closed until finalizers run.
                # Without running them, test__backdoor.Test.test_sys_exit
                # hangs forever
                gc.collect()


class _fileobject(socket._fileobject):

    if not PY3:
        def write(self, data):
            self._sock.sendall(data)
    else:
        def write(self, data):
            if isinstance(data, str):
                data = data.encode('utf-8')
            self._sock.sendall(data)

    def isatty(self):
        return True

    def flush(self):
        pass

    def _readline(self, *a):
        return socket._fileobject.readline(self, *a).replace(b"\r\n", b"\n")
    if not PY3:
        readline = _readline
    else:
        def readline(self, *a):
            line = self._readline(*a)
            return line.decode('utf-8')


if __name__ == '__main__':
    if not sys.argv[1:]:
        print('USAGE: %s PORT' % sys.argv[0])
    else:
        BackdoorServer(('127.0.0.1', int(sys.argv[1])), locals={'hello': 'world'}).serve_forever()
