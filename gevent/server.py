# Copyright (c) 2009-2010 Denis Bilenko. See LICENSE for details.
import sys
import errno
from gevent.greenlet import Greenlet
from gevent.pool import GreenletSet, Pool
from gevent import socket
from gevent import sleep


__all__ = ['StreamServer']

FATAL_ERRORS = (errno.EBADF, errno.EINVAL, errno.ENOTSOCK)


class StreamServer(Greenlet):

    backlog = 256
    min_delay = 0.01
    max_delay = 1
    _allowed_ssl_args = ['keyfile', 'certfile', 'cert_reqs', 'ssl_version', 'ca_certs', 'suppress_ragged_eofs']

    def __init__(self, listener, backlog=None, pool=None, log=sys.stderr, **ssl_args):
        self.ssl_enabled = False
        if hasattr(listener, 'accept'):
            self.socket = listener
            self.address = listener.getsockname()
            self.ssl_enabled = hasattr(listener, 'do_handshake')
        else:
            if not isinstance(listener, tuple):
                raise TypeError('Expected a socket instance or a tuple: %r' % (listener, ))
            if backlog is None:
                backlog = self.backlog
            self.address = listener
            if ssl_args:
                self.ssl_enabled = True
                for key, value in ssl_args:
                    if key not in self._allowed_ssl_args:
                        raise TypeError('Unexpected argument: %r' % (key, ))
                    else:
                        setattr(self, key, value)
        if pool is None:
            self.pool = GreenletSet()
        elif hasattr(pool, 'spawn'):
            self.pool = pool
        elif isinstance(pool, int):
            self.pool = Pool(pool)
        self.log = log
        Greenlet.__init__(self)

    def __str__(self):
        try:
            info = '%s:%s' % self.address
        except Exception, ex:
            info = str(ex) or '<error>'
        return '<%s on %s>' % (self.__class__.__name__, info)

    def log_message(self, message):
        self.log.write(message + '\n')

    @property
    def server_host(self):
        return self.address[0]

    @property
    def server_port(self):
        return self.address[1]

    def pre_start(self):
        if not hasattr(self, 'socket'):
            self.socket = socket.tcp_listener(self.address, backlog=self.backlog)
            self.address = self.socket.getsockname()
            if self.ssl_enabled:
                from gevent.ssl import wrap_socket
                args = {}
                for arg in self._allowed_ssl_args:
                    try:
                        value = getattr(self, arg)
                    except AttributeError:
                        pass
                    else:
                        args[arg] = value
                self.socket = wrap_socket(self.socket, **args)

    def start(self):
        self.pre_start()
        Greenlet.start(self)

    def _run(self):
        try:
            self.delay = self.min_delay
            while True:
                try:
                    client_socket, address = self.socket.accept()
                    self.delay = self.min_delay
                    self.pool.spawn(self.handle, client_socket, address)
                except socket.error, e:
                    if e[0] in FATAL_ERRORS:
                        self.log_message('ERROR: %s failed with %s' % (self, e))
                        return e
                    else:
                        self.log_message('WARNING: %s: ignoring %s (sleeping %s seconds)' % (self, e, self.delay))
                        sleep(self.delay)
                        self.delay = min(self.max_delay, self.delay*2)
        finally:
            try:
                self.socket.close()
            except Exception:
                pass

    def stop(self):
        self.kill(block=True)

    def serve_forever(self):
        if not self: # XXX will this work: server.start(); server.serve_forever()
            self.start()
        self.join()

    def handle(self, socket, address):
        raise NotImplementedError('override in a subclass')



