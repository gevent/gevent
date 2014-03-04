# Copyright (c) 2009-2014 Denis Bilenko and gevent contributors. See LICENSE for details.

"""Cooperative socket module.

This module provides socket operations and some related functions.
The API of the functions and classes matches the API of the corresponding
items in standard :mod:`socket` module exactly, but the synchronous functions
in this module only block the current greenlet and let the others run.

For convenience, exceptions (like :class:`error <socket.error>` and :class:`timeout <socket.timeout>`)
as well as the constants from :mod:`socket` module are imported into this module.
"""

import sys
from gevent.hub import PY3


if PY3:
    from gevent import _socket3 as _source
else:
    from gevent import _socket2 as _source


for key in _source.__dict__:
    if key.startswith('__') and key not in '__implements__ __dns__ __all__ __extensions__ __imports__ __socket__'.split():
        continue
    globals()[key] = getattr(_source, key)


try:
    _GLOBAL_DEFAULT_TIMEOUT = __socket__._GLOBAL_DEFAULT_TIMEOUT
except AttributeError:
    _GLOBAL_DEFAULT_TIMEOUT = object()


def create_connection(address, timeout=_GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Connect to *address* and return the socket object.

    Convenience function.  Connect to *address* (a 2-tuple ``(host,
    port)``) and return the socket object.  Passing the optional
    *timeout* parameter will set the timeout on the socket instance
    before attempting to connect.  If no *timeout* is supplied, the
    global default timeout setting returned by :func:`getdefaulttimeout`
    is used. If *source_address* is set it must be a tuple of (host, port)
    for the socket to bind as a source address before making the connection.
    An host of '' or port 0 tells the OS to use the default.
    """

    host, port = address
    err = None
    for res in getaddrinfo(host, port, 0 if has_ipv6 else AF_INET, SOCK_STREAM):
        af, socktype, proto, _canonname, sa = res
        sock = None
        try:
            sock = socket(af, socktype, proto)
            if timeout is not _GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sa)
            return sock
        except error as ex:
            # without exc_clear(), if connect() fails once, the socket is referenced by the frame in exc_info
            # and the next bind() fails (see test__socket.TestCreateConnection)
            # that does not happen with regular sockets though, because _socket.socket.connect() is a built-in.
            # this is similar to "getnameinfo loses a reference" failure in test_socket.py
            if not PY3:
                sys.exc_clear()
            if sock is not None:
                sock.close()
            err = ex
    if err is not None:
        raise err
    else:
        raise error("getaddrinfo returns an empty list")
