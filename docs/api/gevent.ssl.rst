====================================================================
 :mod:`gevent.ssl` -- Secure Sockets Layer (SSL/TLS) module
====================================================================

.. module:: gevent.ssl

This module provides SSL/TLS operations and some related functions. The
API of the functions and classes matches the API of the corresponding
items in the standard :mod:`ssl` module exactly, but the
synchronous functions in this module only block the current greenlet
and let the others run.

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

.. warning::

   All the described APIs should be imported from
   ``gevent.ssl``, and *not* from their implementation modules.
   Their organization is an implementation detail that may change at
   any time.

.. warning::

   If you will be monkey-patching, it is best to monkey-patch
   *before* the stdlib :mod:`ssl` module has been imported. If you
   patch afterwards, a warning will be emitted. Depending on the exact
   usage of SSL, it is possible that SSL may not work if
   monkey-patching occurs after the import.

   The ``pip_system_certs`` (`source
   <https://gitlab.com/alelec/pip-system-certs/>`_) package uses a
   ``.pth`` file to cause SSL to be imported when Python is started,
   which will result in this warning. See :issue:`2121`.


.. automodule:: gevent.ssl
    :members:
