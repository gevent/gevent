====================================================================
 :mod:`gevent.ssl` -- Secure Sockets Layer (SSL/TLS) module
====================================================================

.. module:: gevent.ssl

This module provides SSL/TLS operations and some related functions. The
API of the functions and classes matches the API of the corresponding
items in the standard :mod:`ssl` module exactly, but the
synchronous functions in this module only block the current greenlet
and let the others run.

The exact API exposed by this module varies depending on what version
of Python you are using. The documents below describe the API for
Python 3, Python 2.7.9 and above, and Python 2.7.8 and below, respectively.

.. tip::

    As an implementation note, gevent's exact behaviour will differ
    somewhat depending on the underlying TLS version in use. For
    example, the number of data exchanges involved in the handshake
    process, and exactly when that process occurs, will vary. This can
    be indirectly observed by the number and timing of greenlet
    switches or trips around the event loop gevent makes.

    Most applications should not notice this, but some applications
    (and especially tests, where it is common for a process to be both
    a server and its own client), may find that they have coded in
    assumptions about the order in which multiple greenlets run. As
    TLS 1.3 gets deployed, those assumptions are likely to break.

.. warning:: All the described APIs should be imported from
   ``gevent.ssl``, and *not* from their implementation modules.
   Their organization is an implementation detail that may change at
   any time.

.. class:: SSLObject

    The gevent-cooperative SSL object. See the version-specific
    documentation for details.

.. toctree::

   Python 3 interface <gevent._ssl3>
   Python 2.7.9 and above interface (including PyPy 2.6.1 and above) <gevent._sslgte279>
   Python 2.7.8 and below interface <gevent._ssl2>
