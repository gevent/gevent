gevent is a coroutine_ -based Python_ networking library that uses
greenlet_ to provide a high-level synchronous API on top of the `libev`_
or `libuv`_ event loop.

Features include:


* Fast event loop based on `libev`_ or `libuv`_
* Lightweight execution units based on greenlet_.
* API that re-uses concepts from the Python standard library (for
  examples there are :class:`events <gevent.event.Event>` and
  :class:`queues <gevent.queue.Queue>`).
* :ref:`Cooperative sockets with SSL support <networking>`
* :doc:`Cooperative DNS queries <dns>` performed through a threadpool,
  dnspython, or c-ares.
* :ref:`Monkey patching utility <monkey-patching>` to get 3rd party modules to become cooperative
* TCP/UDP/HTTP servers
* Subprocess support (through :mod:`gevent.subprocess`)
* Thread pools

.. _coroutine: https://en.wikipedia.org/wiki/Coroutine
.. _Python: http://python.org
.. _greenlet: https://greenlet.readthedocs.io
.. _libev: http://software.schmorp.de/pkg/libev.html
.. _libuv: http://libuv.org
