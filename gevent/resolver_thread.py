# Copyright (c) 2012-2015 Denis Bilenko. See LICENSE for details.
"""
Native thread-based hostname resolver.
"""
import _socket
from gevent.hub import get_hub, text_type


__all__ = ['Resolver']


# trigger import of encodings.idna to avoid https://github.com/gevent/gevent/issues/349
text_type('foo').encode('idna')


class Resolver(object):
    """
    Implementation of the resolver API using native threads and native resolution
    functions.

    Using the native resolution mechanisms ensures the highest
    compatibility with what a non-gevent program would return
    including good support for platform specific configuration
    mechanisms. The use of native (non-greenlet) threads ensures that
    a caller doesn't block other greenlets.

    This implementation also has the benefit of being very simple in comparison to
    :class:`gevent.resolver_ares.Resolver`.

    .. tip::

        Most users find this resolver to be quite reliable in a
        properly monkey-patched environment. However, there have been
        some reports of long delays, slow performance or even hangs,
        particularly in long-lived programs that make many, many DNS
        requests. If you suspect that may be happening to you, try the
        ares resolver (and submit a bug report).
    """
    def __init__(self, hub=None):
        if hub is None:
            hub = get_hub()
        self.pool = hub.threadpool
        if _socket.gaierror not in hub.NOT_ERROR:
            # Do not cause lookup failures to get printed by the default
            # error handler. This can be very noisy.
            hub.NOT_ERROR += (_socket.gaierror, _socket.herror)

    def __repr__(self):
        return '<gevent.resolver_thread.Resolver at 0x%x pool=%r>' % (id(self), self.pool)

    def close(self):
        pass

    # from briefly reading socketmodule.c, it seems that all of the functions
    # below are thread-safe in Python, even if they are not thread-safe in C.

    def gethostbyname(self, *args):
        return self.pool.apply(_socket.gethostbyname, args)

    def gethostbyname_ex(self, *args):
        return self.pool.apply(_socket.gethostbyname_ex, args)

    def getaddrinfo(self, *args, **kwargs):
        return self.pool.apply(_socket.getaddrinfo, args, kwargs)

    def gethostbyaddr(self, *args, **kwargs):
        return self.pool.apply(_socket.gethostbyaddr, args, kwargs)

    def getnameinfo(self, *args, **kwargs):
        return self.pool.apply(_socket.getnameinfo, args, kwargs)
