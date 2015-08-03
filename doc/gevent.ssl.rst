====================================================================
 :mod:`gevent.ssl` -- Secure Sockets Layer (SSL/TLS) module
====================================================================

This module provides SSL/TLS operations and some related functions. The
API of the functions and classes matches the API of the corresponding
items in the standard :mod:`ssl` module exactly, but the
synchronous functions in this module only block the current greenlet
and let the others run.

The exact API exposed by this module varies depending on what version
of Python you are using. The documents below describe the API for
Python 3, Python 2.7.9 and above, and Python 2.7.8 and below, respectively.

.. warning:: All the described APIs should be imported from
   ``gevent.ssl``, and *not* from their implementation modules.
   Their organization is an implementation detail that may change at
   any time.

.. toctree::

   Python 3 interface <gevent._ssl3>
   Python 2.7.9 and above interface (including PyPy 2.6.0) <gevent._sslgte279>
   Python 2.7.8 and below interface (including PyPy 2.5.0) <gevent._ssl2>
