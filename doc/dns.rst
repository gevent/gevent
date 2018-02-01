=======================
 Name Resolution (DNS)
=======================

gevent includes support for a pluggable hostname resolution system.
Pluggable resolvers are (generally) intended to be cooperative.
This pluggable resolution system is used automatically when the system
is :mod:`monkey patched <gevent.monkey>`, and may be used manually
through the :attr:`resolver attribute <gevent.hub.Hub.resolver>` of the
:class:`gevent.hub.Hub` or the corresponding methods in the
:mod:`gevent.socket` module.

A resolver implements the 5 standandard functions from the
:mod:`socket` module for resolving hostnames and addresses:

* :func:`socket.gethostbyname`
* :func:`socket.gethostbyname_ex`
* :func:`socket.getaddrinfo`
* :func:`socket.gethostbyaddr`
* :func:`socket.getnameinfo`

Configuration
=============

gevent includes four implementations of resolvers, and applications
can provide their own implementation. By default, gevent uses
:class:`gevent.resolver.thread.Resolver`.

Configuration can be done through the ``GEVENT_RESOLVER`` environment
variable. Specify ``ares``, ``thread``, ``dnspython``, or ``block`` to use the
:class:`gevent.resolver.ares.Resolver`,
:class:`gevent.resolver.thread.Resolver`, or
:class:`gevent.resolver.dnspython.Resolver`, or
:class:`gevent.resolver.blocking.Resolver`, respectively, or set it to
the fully-qualified name of an implementation of the standard
functions.

Please see the documentation for each resolver class to understand the
relative performance and correctness tradeoffs.

.. toctree::

   gevent.resolver.thread
   gevent.resolver.ares
   gevent.resolver.dnspython
   gevent.resolver.blocking
