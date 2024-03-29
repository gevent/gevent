..
  This file is included in README.rst from the top-level
  so it is limited to pure ReST markup, not Sphinx.



gevent is a coroutine_ -based Python_ networking library that uses
`greenlet <https://greenlet.readthedocs.io>`_ to provide a high-level synchronous API on top of the `libev`_
or `libuv`_ event loop.

Features include:


* Fast event loop based on `libev`_ or `libuv`_.
* Lightweight execution units based on greenlets.
* API that re-uses concepts from the Python standard library (for
  examples there are `events`_ and
  `queues`_).
* `Cooperative sockets with SSL support <http://www.gevent.org/api/index.html#networking>`_
* `Cooperative DNS queries <http://www.gevent.org/dns.html>`_ performed through a threadpool,
  dnspython, or c-ares.
* `Monkey patching utility <http://www.gevent.org/intro.html#monkey-patching>`_ to get 3rd party modules to become cooperative
* TCP/UDP/HTTP servers
* Subprocess support (through `gevent.subprocess`_)
* Thread pools

gevent is `inspired by eventlet`_ but features a more consistent API,
simpler implementation and better performance. Read why others `use
gevent`_ and check out the list of the `open source projects based on
gevent`_.

gevent was written by `Denis Bilenko <http://denisbilenko.com/>`_.

Since version 1.1, gevent is maintained by Jason Madden for
`NextThought <https://nextthought.com>`_ (through gevent 21) and
`Institutional Shareholder Services <https://www.issgovernance.com>`_
with help from the `contributors
<https://github.com/gevent/gevent/graphs/contributors>`_ and is
licensed under the MIT license.

See `what's new`_ in the latest major release.

Check out the detailed changelog_ for this version.

.. _events: http://www.gevent.org/api/gevent.event.html#gevent.event.Event
.. _queues: http://www.gevent.org/api/gevent.queue.html#gevent.queue.Queue
.. _gevent.subprocess: http://www.gevent.org/api/gevent.subprocess.html#module-gevent.subprocess

.. _coroutine: https://en.wikipedia.org/wiki/Coroutine
.. _Python: http://python.org
.. _libev: http://software.schmorp.de/pkg/libev.html
.. _libuv: http://libuv.org
.. _inspired by eventlet: http://blog.gevent.org/2010/02/27/why-gevent/
.. _use gevent: http://groups.google.com/group/gevent/browse_thread/thread/4de9703e5dca8271
.. _open source projects based on gevent: https://github.com/gevent/gevent/wiki/Projects
.. _what's new: http://www.gevent.org/whatsnew_1_5.html
.. _changelog: http://www.gevent.org/changelog.html
