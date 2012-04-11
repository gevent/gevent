gevent_
=======

.. attention::

  New_ version of gevent uses libev_ and c-ares rather than libevent and includes all the dependencies in the release tarball.

  You can download the 1.0 beta release from `google code`_. Please give it a try.

.. _libev: http://blog.gevent.org/2011/04/28/libev-and-libevent/
.. _google code: http://code.google.com/p/gevent/downloads/
.. _New: https://bitbucket.org/denis/gevent/src/tip/changelog.rst#cl-7

gevent_ is a Python networking library that uses greenlet_ to provide synchronous API on top of libevent_ event loop.

Features include:

* Fast event loop based on libevent_.
* Lightweight execution units based on greenlet_.
* Familiar API that re-uses concepts from the Python standard library.
* Cooperative sockets with ssl support.
* DNS queries performed through libevent-dns.
* Ability to use standard library and 3rd party modules written for standard blocking sockets
* Fast WSGI server based on libevent-http.

gevent_ is `inspired by eventlet`_ but features more consistent API, simpler implementation and better performance. Read why others `use gevent`_ and check out the list of the `open source projects based on gevent`_.

gevent_ is written and maintained by `Denis Bilenko`_ and is licensed under MIT license.


get gevent
----------

Install Python 2.4 or newer, greenlet and libevent.

Download the latest release from `Python Package Index`_ or clone `the repository`_.

Read the documentation online at http://www.gevent.org

Post feedback and issues on the `bug tracker`_, `mailing list`_, blog_ and `twitter (@gevent)`_.


.. _gevent: http://www.gevent.org
.. _greenlet: http://codespeak.net/py/0.9.2/greenlet.html
.. _libevent: http://monkey.org/~provos/libevent/
.. _inspired by eventlet: http://blog.gevent.org/2010/02/27/why-gevent/
.. _use gevent: http://groups.google.com/group/gevent/browse_thread/thread/4de9703e5dca8271
.. _open source projects based on gevent: http://code.google.com/p/gevent/wiki/ProjectsUsingGevent
.. _Denis Bilenko: http://denisbilenko.com
.. _Python Package Index: http://pypi.python.org/pypi/gevent
.. _the repository: http://bitbucket.org/denis/gevent
.. _bug tracker: http://code.google.com/p/gevent/issues/list
.. _mailing list: http://groups.google.com/group/gevent
.. _blog: http://blog.gevent.org
.. _twitter (@gevent): http://twitter.com/gevent

