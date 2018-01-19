# Copyright (c) 2009-2014, gevent contributors
# Based on eventlet.backdoor Copyright (c) 2005-2006, Bob Ippolito
"""
Interactive greenlet-based network console that can be used in any process.

The :class:`BackdoorServer` provides a REPL inside a running process. As
long as the process is monkey-patched, the ``BackdoorServer`` can coexist
with other elements of the process.

.. seealso:: :class:`code.InteractiveConsole`
"""
from __future__ import print_function, absolute_import
import sys
from code import InteractiveConsole

from gevent.greenlet import Greenlet
from gevent.hub import getcurrent
from gevent.server import StreamServer
from gevent.pool import Pool

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
    # A greenlet that replaces sys.std[in/out/err] while running.
    _fileobj = None
    saved = None

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

    def throw(self, *args, **kwargs):
        # pylint:disable=arguments-differ
        if self.saved is None and self._fileobj is not None:
            self.switch_in()
        Greenlet.throw(self, *args, **kwargs)

    def run(self):
        try:
            return Greenlet.run(self)
        finally:
            # Make sure to restore the originals.
            self.switch_out()


class BackdoorServer(StreamServer):
    """
    Provide a backdoor to a program for debugging purposes.

    .. warning:: This backdoor provides no authentication and makes no
          attempt to limit what remote users can do. Anyone that
          can access the server can take any action that the running
          python process can. Thus, while you may bind to any interface, for
          security purposes it is recommended that you bind to one
          only accessible to the local machine, e.g.,
          127.0.0.1/localhost.

    Basic usage::

        from gevent.backdoor import BackdoorServer
        server = BackdoorServer(('127.0.0.1', 5001),
                                banner="Hello from gevent backdoor!",
                                locals={'foo': "From defined scope!"})
        server.serve_forever()

    In a another terminal, connect with...::

        $ telnet 127.0.0.1 5001
        Trying 127.0.0.1...
        Connected to 127.0.0.1.
        Escape character is '^]'.
        Hello from gevent backdoor!
        >> print(foo)
        From defined scope!

    .. versionchanged:: 1.2a1
       Spawned greenlets are now tracked in a pool and killed when the server
       is stopped.
    """

    def __init__(self, listener, locals=None, banner=None, **server_args):
        """
        :keyword locals: If given, a dictionary of "builtin" values that will be available
            at the top-level.
        :keyword banner: If geven, a string that will be printed to each connecting user.
        """
        group = Pool(greenlet_class=_Greenlet_stdreplace) # no limit on number
        StreamServer.__init__(self, listener, spawn=group, **server_args)
        _locals = {'__doc__': None, '__name__': '__console__'}
        if locals:
            _locals.update(locals)
        self.locals = _locals

        self.banner = banner
        self.stderr = sys.stderr

    def _create_interactive_locals(self):
        # Create and return a *new* locals dictionary based on self.locals,
        # and set any new entries in it. (InteractiveConsole does not
        # copy its locals value)
        _locals = self.locals.copy()
        # __builtins__ may either be the __builtin__ module or
        # __builtin__.__dict__; in the latter case typing
        # locals() at the backdoor prompt spews out lots of
        # useless stuff
        try:
            import __builtin__
            _locals["__builtins__"] = __builtin__
        except ImportError:
            import builtins # pylint:disable=import-error
            _locals["builtins"] = builtins
            _locals['__builtins__'] = builtins
        return _locals

    def handle(self, conn, _address): # pylint: disable=method-hidden
        """
        Interact with one remote user.

        .. versionchanged:: 1.1b2 Each connection gets its own
            ``locals`` dictionary. Previously they were shared in a
            potentially unsafe manner.
        """
        fobj = conn.makefile(mode="rw")
        fobj = _fileobject(conn, fobj, self.stderr)
        getcurrent()._fileobj = fobj

        getcurrent().switch_in()
        try:
            console = InteractiveConsole(self._create_interactive_locals())
            if sys.version_info[:3] >= (3, 6, 0):
                # Beginning in 3.6, the console likes to print "now exiting <class>"
                # but probably our socket is already closed, so this just causes problems.
                console.interact(banner=self.banner, exitmsg='') # pylint:disable=unexpected-keyword-arg
            else:
                console.interact(banner=self.banner)
        except SystemExit:  # raised by quit()
            if hasattr(sys, 'exc_clear'): # py2
                sys.exc_clear()
        finally:
            conn.close()
            fobj.close()


class _fileobject(object):
    """
    A file-like object that wraps the result of socket.makefile (composition
    instead of inheritance lets us work identically under CPython and PyPy).

    We write directly to the socket, avoiding the buffering that the text-oriented
    makefile would want to do (otherwise we'd be at the mercy of waiting on a
    flush() to get called for the remote user to see data); this beats putting
    the file in binary mode and translating everywhere with a non-default
    encoding.
    """
    def __init__(self, sock, fobj, stderr):
        self._sock = sock
        self._fobj = fobj
        self.stderr = stderr

    def __getattr__(self, name):
        return getattr(self._fobj, name)

    def close(self):
        self._fobj.close()
        self._sock.close()

    def write(self, data):
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
        self._sock.sendall(data)

    def isatty(self):
        return True

    def flush(self):
        pass

    def readline(self, *a):
        try:
            return self._fobj.readline(*a).replace("\r\n", "\n")
        except UnicodeError:
            # Typically, under python 3, a ^C on the other end
            return ''


if __name__ == '__main__':
    if not sys.argv[1:]:
        print('USAGE: %s PORT [banner]' % sys.argv[0])
    else:
        BackdoorServer(('127.0.0.1', int(sys.argv[1])),
                       banner=(sys.argv[2] if len(sys.argv) > 2 else None),
                       locals={'hello': 'world'}).serve_forever()
