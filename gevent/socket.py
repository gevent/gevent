# Copyright (c) 2009-2014 Denis Bilenko and gevent contributors. See LICENSE for details.

"""Cooperative low-level networking interface.

This module provides socket operations and some related functions.
The API of the functions and classes matches the API of the corresponding
items in the standard :mod:`socket` module exactly, but the synchronous functions
in this module only block the current greenlet and let the others run.

For convenience, exceptions (like :class:`error <socket.error>` and :class:`timeout <socket.timeout>`)
as well as the constants from the :mod:`socket` module are imported into this module.
"""
# Our import magic sadly makes this warning useless
# pylint: disable=undefined-variable

import sys
from gevent._compat import PY3
from gevent._util import copy_globals


if PY3:
    from gevent import _socket3 as _source # python 2: pylint:disable=no-name-in-module
else:
    from gevent import _socket2 as _source

# define some things we're expecting to overwrite; each module
# needs to define these
__implements__ = __dns__ = __all__ = __extensions__ = __imports__ = ()


class error(Exception):
    errno = None


def getfqdn(*args):
    # pylint:disable=unused-argument
    raise NotImplementedError()

copy_globals(_source, globals(),
             dunder_names_to_keep=('__implements__', '__dns__', '__all__',
                                   '__extensions__', '__imports__', '__socket__'),
             cleanup_globs=False)

# The _socket2 and _socket3 don't import things defined in
# __extensions__, to help avoid confusing reference cycles in the
# documentation and to prevent importing from the wrong place, but we
# *do* need to expose them here. (NOTE: This may lead to some sphinx
# warnings like:
#    WARNING: missing attribute mentioned in :members: or __all__:
#             module gevent._socket2, attribute cancel_wait
# These can be ignored.)
from gevent import _socketcommon
copy_globals(_socketcommon, globals(),
             only_names=_socketcommon.__extensions__)

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
    A host of '' or port 0 tells the OS to use the default.
    """

    host, port = address
    err = None
    for res in getaddrinfo(host, port, 0 if has_ipv6 else AF_INET, SOCK_STREAM):
        af, socktype, proto, _, sa = res
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
                sys.exc_clear() # pylint:disable=no-member,useless-suppression
            if sock is not None:
                sock.close()
            err = ex
    if err is not None:
        raise err # pylint:disable=raising-bad-type
    else:
        raise error("getaddrinfo returns an empty list")

# This is promised to be in the __all__ of the _source, but, for circularity reasons,
# we implement it in this module. Mostly for documentation purposes, put it
# in the _source too.
_source.create_connection = create_connection
