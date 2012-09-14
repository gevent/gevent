gevent_
=======

gevent_ is a coroutine-based Python networking library.

Features include:

* Fast event loop based on libev_.
* Lightweight execution units based on greenlet_.
* Familiar API that re-uses concepts from the Python standard library.
* Cooperative sockets with SSL support.
* DNS queries performed through c-ares_ or a threadpool.
* Ability to use standard library and 3rd party modules written for standard blocking sockets

gevent_ is `inspired by eventlet`_ but features more consistent API, simpler implementation and better performance. Read why others `use gevent`_ and check out the list of the `open source projects based on gevent`_.

gevent_ is written and maintained by `Denis Bilenko`_ and is licensed under MIT license.


get gevent
----------

Install Python 2.5 or newer and greenlet_ extension.

Download the latest release from `Python Package Index`_ or clone `the repository`_.

Read the documentation online at http://www.gevent.org

Post feedback and issues on the `bug tracker`_, `mailing list`_, blog_ and `twitter (@gevent)`_.


.. _gevent: http://www.gevent.org
.. _greenlet: http://pypi.python.org/pypi/greenlet
.. _libev: http://libev.schmorp.de/
.. _c-ares: http://c-ares.haxx.se/
.. _inspired by eventlet: http://blog.gevent.org/2010/02/27/why-gevent/
.. _use gevent: http://groups.google.com/group/gevent/browse_thread/thread/4de9703e5dca8271
.. _open source projects based on gevent: http://code.google.com/p/gevent/wiki/ProjectsUsingGevent
.. _Denis Bilenko: http://denisbilenko.com
.. _Python Package Index: http://pypi.python.org/pypi/gevent
.. _the repository: https://github.com/sitesupport/gevent
.. _bug tracker: https://github.com/SiteSupport/gevent/wiki/Projects
.. _mailing list: http://groups.google.com/group/gevent
.. _blog: http://blog.gevent.org
.. _twitter (@gevent): http://twitter.com/gevent

