# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.
"""TCP/SSL server"""
import sys
import errno
import traceback
from gevent import socket
from gevent import core
from gevent.baseserver import BaseServer


__all__ = ['StreamServer']


class StreamServer(BaseServer):
    """A generic TCP server. Accepts connections on a listening socket and spawns user-provided *handle*
    for each connection with 2 arguments: the client socket and the client address.

    If any of the following keyword arguments are present, then the server assumes SSL mode and uses these arguments
    to create an SSL wrapper for the client socket before passing it to *handle*:

    - keyfile
    - certfile
    - cert_reqs
    - ssl_version
    - ca_certs
    - suppress_ragged_eofs

    Note that although the errors in a successfully spawned handler will not affect the server or other connections,
    the errors raised by :func:`accept` and *spawn* cause the server to stop accepting for a short amount of time. The
    exact period depends on the values of :attr:`min_delay` and :attr:`max_delay` attributes.

    The delay starts with :attr:`min_delay` and doubles with each successive error until it reaches :attr:`max_delay`.
    A successful :func:`accept` resets the delay to :attr:`min_delay` again.
    """

    # the number of seconds to sleep in case there was an error in accept() call
    # for consecutive errors the delay will double until it reaches max_delay
    # when accept() finally succeeds the delay will be reset to min_delay again
    min_delay = 0.01
    max_delay = 1

    _allowed_ssl_args = ('keyfile', 'certfile', 'cert_reqs', 'ssl_version', 'ca_certs', 'suppress_ragged_eofs')

    def __init__(self, listener, handle=None, backlog=None, spawn='default', **ssl_args):
        if ssl_args:
            for arg in ssl_args:
                if arg not in self._allowed_ssl_args:
                    raise TypeError('StreamServer.__init__() got an unexpected keyword argument %r' % arg)
            try:
                from gevent.ssl import wrap_socket
            except ImportError:
                wrap_socket = _import_sslold_wrap_socket()
                if wrap_socket is None:
                    raise
            self.wrap_socket = wrap_socket
            self.ssl_args = ssl_args
            self.ssl_enabled = True
        else:
            self.ssl_enabled = False
        BaseServer.__init__(self, listener, handle=handle, backlog=backlog, spawn=spawn)
        self.delay = self.min_delay
        self._accept_event = None
        self._start_accepting_timer = None

    def set_listener(self, listener, backlog=None):
        BaseServer.set_listener(self, listener, backlog=backlog)
        try:
            self.socket = self.socket._sock
        except AttributeError:
            pass

    def set_spawn(self, spawn):
        BaseServer.set_spawn(self, spawn)
        if self.pool is not None:
            self.pool._semaphore.rawlink(self._start_accepting)

    def set_handle(self, handle):
        BaseServer.set_handle(self, handle)
        # make SSL work:
        if self.ssl_enabled:
            self._handle = self.wrap_socket_and_handle
        else:
            self._handle = self.handle

    @property
    def started(self):
        return self._accept_event is not None or self._start_accepting_timer is not None

    def start_accepting(self):
        if self._accept_event is None:
            self._accept_event = core.read_event(self.socket.fileno(), self._do_accept, persist=True)

    def _start_accepting(self, _event):
        if self._accept_event is None:
            if 'socket' not in self.__dict__:
                return
            self._accept_event = core.read_event(self.socket.fileno(), self._do_accept, persist=True)

    def stop_accepting(self):
        if self._accept_event is not None:
            self._accept_event.cancel()
            self._accept_event = None
        if self._start_accepting_timer is not None:
            self._start_accepting_timer.cancel()
            self._start_accepting_timer = None

    def _do_accept(self, event, _evtype):
        assert event is self._accept_event
        address = None
        try:
            if self.full():
                self.stop_accepting()
                return
            try:
                client_socket, address = self.socket.accept()
            except socket.error, err:
                if err[0]==errno.EAGAIN:
                    sys.exc_clear()
                    return
                raise

            self.delay = self.min_delay
            client_socket = socket.socket(_sock=client_socket)
            spawn = self._spawn
            if spawn is None:
                self._handle(client_socket, address)
            else:
                spawn(self._handle, client_socket, address)
            return
        except:
            traceback.print_exc()
            ex = sys.exc_info()[1]
            if self.is_fatal_error(ex):
                self.kill()
                sys.stderr.write('ERROR: %s failed with %s\n' % (self, str(ex) or repr(ex)))
                return
        try:
            if address is None:
                sys.stderr.write('%s: Failed.\n' % (self, ))
            else:
                sys.stderr.write('%s: Failed to handle request from %s\n' % (self, address, ))
        except Exception:
            traceback.print_exc()
        if self.delay >= 0:
            self.stop_accepting()
            self._start_accepting_timer = core.timer(self.delay, self.start_accepting)
            self.delay = min(self.max_delay, self.delay*2)
        sys.exc_clear()

    def is_fatal_error(self, ex):
        return isinstance(ex, socket.error) and ex[0] in (errno.EBADF, errno.EINVAL, errno.ENOTSOCK)

    def wrap_socket_and_handle(self, client_socket, address):
        # used in case of ssl sockets
        ssl_socket = self.wrap_socket(client_socket, server_side=True, **self.ssl_args)
        return self.handle(ssl_socket, address)


def _import_sslold_wrap_socket():
    try:
        from gevent.sslold import wrap_socket
        return wrap_socket
    except ImportError:
        pass

