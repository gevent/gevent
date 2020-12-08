===============
 API reference
===============

Functional Areas
================

This section of the document groups gevent APIs by functional area.
For an alphabetical listing by module, see :ref:`api_module_listing`.

High-level concepts
-------------------
.. toctree::

   gevent
   gevent.timeout
   gevent.greenlet

.. _networking:

Networking interfaces
---------------------

.. toctree::

   gevent.socket
   gevent.ssl
   gevent.select
   gevent.selectors

Synchronization primitives (locks, queues, events)
--------------------------------------------------

.. toctree::

   gevent.event
   gevent.queue
   gevent.local
   gevent.lock

Low-level details
-----------------

.. toctree::

   gevent.hub
   gevent.core

.. _api_module_listing:

Module Listing
==============

This section of the document groups gevent APIs by module.

.. This should be sorted alphabetically

.. toctree::

   gevent
   gevent.backdoor
   gevent.baseserver
   gevent.builtins
   gevent.contextvars
   gevent.core
   gevent.event
   gevent.events
   gevent.exceptions
   gevent.fileobject
   gevent.hub
   gevent.local
   gevent.lock
   gevent.monkey
   gevent.os
   gevent.pool
   gevent.pywsgi
   gevent.queue
   gevent.resolver.ares
   gevent.resolver.blocking
   gevent.resolver.dnspython
   gevent.resolver.thread
   gevent.select
   gevent.server
   gevent.signal
   gevent.socket
   gevent.ssl
   gevent.subprocess
   gevent.thread
   gevent.threading
   gevent.threadpool
   gevent.time
   gevent.util


Deprecated Modules
------------------

These modules are deprecated and should not be used in new code.

.. toctree::

   gevent.ares
   gevent.wsgi

Examples
========

.. toctree::

   /examples/index
