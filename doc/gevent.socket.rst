====================================================================
 :mod:`gevent.socket` -- Cooperative low-level networking interface
====================================================================

This module provides socket operations and some related functions. The
API of the functions and classes matches the API of the corresponding
items in the standard :mod:`socket` module exactly, but the
synchronous functions in this module only block the current greenlet
and let the others run.

For convenience, exceptions (like :class:`error <socket.error>` and
:class:`timeout <socket.timeout>`) as well as the constants from the
:mod:`socket` module are imported into this module.


The exact API exposed by this module varies depending on what version
of Python you are using. The documents below describe the API for
Python 2 and Python 3, respectively.

.. warning:: All the described APIs should be imported from
   ``gevent.socket``, and *not* from their implementation modules.
   Their organization is an implementation detail that may change at
   any time.

.. toctree::

   Python 3 interface <gevent._socket3>
   Python 2 interface <gevent._socket2>


Shared Functions
================

These functions are identical and shared by all implementations.

.. autofunction:: gevent.socket.create_connection
