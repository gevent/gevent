=================
 What is gevent?
=================

gevent is a coroutine_ -based Python_ networking library that uses
greenlet_ to provide a high-level synchronous API on top of the libev
event loop.

Features include:

* **Fast event loop** based on libev (epoll on Linux, kqueue on FreeBSD).
* **Lightweight execution units** based on greenlet.
* API that re-uses concepts from the Python standard library (for example there are :class:`gevent.event.Events` and :class:`gevent.queue.Queues`).
* :doc:`Cooperative sockets with SSL support <networking>`
* DNS queries performed through threadpool or c-ares.
* :ref:`Monkey patching utility <monkey-patching>` to get 3rd party modules to become cooperative


gevent is `inspired by eventlet
<http://blog.gevent.org/2010/02/27/why-gevent/>`_ but features more
consistent API, simpler implementation and better performance. Read
why others `use gevent
<http://groups.google.com/group/gevent/browse_thread/thread/4de9703e5dca8271>`_
and check out the list of the `open source projects based on gevent. <http://code.google.com/p/gevent/wiki/ProjectsUsingGevent>`_

gevent is written and maintained by `Denis Bilenko
<http://denisbilenko.com/>`_ with help from the `contributors <https://github.com/gevent/gevent/blob/master/AUTHORS#L1>`_ and is licensed under the MIT license.

:ref:`Continue reading <installation>` »

If you like gevent, :doc:`donate <sfc>` to support the development.

What are others saying?
=======================

Twitter @gevent
---------------

.. raw:: html

   <a class="twitter-timeline" data-dnt="true" href="https://twitter.com/search?q=%40gevent%20include%3Aretweets" data-widget-id="621692925999644672">Tweets about gevent</a> <script>!function(d,s,id){var js,fjs=d.getElementsByTagName(s)[0],p=/^http:/.test(d.location)?'http':'https';if(!d.getElementById(id)){js=d.createElement(s);js.id=id;js.src=p+"://platform.twitter.com/widgets.js";fjs.parentNode.insertBefore(js,fjs);}}(document,"script","twitter-wjs");</script>


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
.. _greenlet: http://greenlet.readthedocs.org
