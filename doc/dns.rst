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
:class:`a threadpool <gevent.resolver.thread.Resolver>`. This can
:attr:`be customized <gevent._config.Config.resolver>`.

Please see the documentation for each resolver class to understand the
relative performance and correctness tradeoffs.

.. toctree::

   api/gevent.resolver.thread
   api/gevent.resolver.ares
   api/gevent.resolver.dnspython
   api/gevent.resolver.blocking
