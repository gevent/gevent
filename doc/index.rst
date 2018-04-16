=================
 What is gevent?
=================

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
* :doc:`Cooperative DNS queries <dns>` performed through a threadpool, dnspython, or c-ares.
* :ref:`Monkey patching utility <monkey-patching>` to get 3rd party modules to become cooperative
* TCP/UDP/HTTP servers
* Subprocess support (through :mod:`gevent.subprocess`)
* Thread pools


gevent is `inspired by eventlet
<http://blog.gevent.org/2010/02/27/why-gevent/>`_ but features more
consistent API, simpler implementation and better performance. Read
why others `use gevent
<http://groups.google.com/group/gevent/browse_thread/thread/4de9703e5dca8271>`_
and check out the list of the `open source projects based on gevent. <https://github.com/gevent/gevent/wiki/Projects>`_

gevent was written by `Denis Bilenko <http://denisbilenko.com/>`_.

Since version 1.1, gevent is maintained by Jason Madden for
`NextThought <https://nextthought.com>`_ with help from the
`contributors <https://github.com/gevent/gevent/graphs/contributors>`_.

gevent is licensed under the MIT license.

:ref:`Continue reading <installation>` »

If you like gevent, :doc:`donate <sfc>` to support the development.

What are others saying?
=======================


Mailing List
------------

.. raw:: html

   <iframe id="forum_embed"
         src="javascript:void(0)"
         scrolling="no"
         frameborder="0"
         width="100%"
         height="500">
   </iframe>

   <script type="text/javascript">
         document.getElementById("forum_embed").src = "https://groups.google.com/forum/embed/?place=forum/gevent"
             + "&showsearch=false&showtabs=false&hideforumtitle=true&showpopout=true&parenturl=" + encodeURIComponent(window.location.href);
   </script>

.. _coroutine: https://en.wikipedia.org/wiki/Coroutine
.. _Python: http://python.org
.. _greenlet: https://greenlet.readthedocs.io
.. _libev: http://software.schmorp.de/pkg/libev.html
.. _libuv: http://libuv.org
