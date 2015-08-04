=======================
 Name Resolution (DNS)
=======================

gevent includes support for a pluggable hostname resolution system.
Pluggable resolvers are (generally) intended to be cooperative.
This pluggable resolution system is used automatically when the system
is :mod:`monkey patched <gevent.monkey>`, and may be used manually
through the :attr:`resolver attribute <gevent.Hub.resolver>` of the
:class:`gevent.hub.Hub` or the corresponding methods in the
:mod:`gevent.socket` module.

A resolver implements the 5 standandard functions from the
:mod:`socket` module for resolving hostnames:

* :func:`socket.gethostbyname`
* :func:`socket.gethostbyname_ex`
* :func:`socket.getaddrinfo`
* :func:`socket.gethostbyaddr`
* :func:`socket.getnameinfo`

Configuration
=============

gevent includes three implementations of resolvers, and applications
can provide their own implementation. By default, gevent uses
:class:`gevent.resolver_thread.Resolver`.

Configuration can be done through the ``GEVENT_RESOLVER`` environment
variable. Specify ``ares``, ``thread``, or ``block`` to use the
:class:`gevent.resolver_ares.Resolver`,
:class:`gevent.resolver_thread.Resolver`, or
:class:`gevent.socket.BlockingResolver`, respectively, or set it to
the fully-qualified name of an implementation of the standard
functions.

.. toctree::

   gevent.resolver_thread
   gevent.resolver_ares
