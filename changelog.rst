Changelog
=========

.. currentmodule:: gevent

Version 0.11.2
--------------

* Fixed :mod:`wsgi` to unquote ``environ['PATH_INFO']`` before passing to application.
* Added ``SERVER_SOFTWARE`` variable to :mod:`wsgi` environ.

* Fixed bug in :meth:`JoinableQueue.task_done` that caused :class:`ValueError` to be raised incorrectly here.
* Fixed :mod:`gevent.socket` not to fail with :class:`ImportError` if Python was not built with ssl support.


Version 0.11.1
--------------

* Fixed bug in :func:`select.select` function. Passing non-empty list of write descriptors used to cause this function to fail.
* Changed setup.py to go ahead with the compilation even if the actual version of libevent cannot be determined (version 1.x.x is assumed in that case).

Contributed by **Ludvig Ericson**:

* Fixed :mod:`wsgi`'s ``start_response`` to recognize *exc_info* argument.
* Fixed setup.py to look for libevent.dylib rather than .so on Darwin platforms.


Version 0.11.0
--------------

* Fixed timeout bug in :func:`joinall`, :meth:`Greenlet.join`, :meth:`pool.Pool.join`: if timeout has expired
  it used to raise :class:`Timeout`; now it returns silently.
* Fixed :func:`signal` to run the signal handler in a new greenlet; it was run in the :class:`Hub` greenlet before.
* Fixed :meth:`Timeout.start_new`: if passed a :class:`Timeout` instance, it now calls its :meth:`start <Timeout.start>`
  method before returning it.
* Fixed :mod:`gevent.monkey` to patch :class:`threading.local` properly.
* Fixed :meth:`Queue.empty` and :meth:`Queue.full` to be compatible
  with the standard :mod:`Queue`. It tried to take into account the greenlets currently blocking on
  :meth:`get <Queue.get>`/:meth:`put <Queue.put>` which
  was not useful and hard to reason about. Now it simply compares :meth:`qsize <Queue.qsize>` to *maxsize*,
  which what the standard :mod:`Queue` does too.
* Fixed :class:`Event` to behave exactly like the standard :class:`threading.Event`:

  - :meth:`Event.set` does not accept a parameter anymore; it's now either set or not.
  - ``Event.get`` method is gone.
  - ``Event.set(); Event.clear()`` used to be a no-op; now it properly wakes up all the waiters.
  - :class:`AsyncResult` behaves exactly like before, but it does not inherit from :class:`Event` anymore
    and does miss ``clear()`` method.

* Renamed internal helpers :meth:`socket.wait_reader`/:meth:`socket.wait_writer` to :meth:`socket.wait_read`/:meth:`socket.wait_write`.
* Renamed :class:`gevent.socket.GreenSocket` to :class:`gevent.socket.socket`. ``GreenSocket`` is still available
  as an alias but will be removed in the future.
* :mod:`gevent.core` now includes wrappers for evbuffer, evdns, evhttp.
* Renamed the old ``gevent.wsgi`` to :mod:`gevent.pywsgi`.
* Added a new HTTP server :mod:`gevent.http` module based on libevent-http wrappers.
* Added a new WSGI server :mod:`gevent.wsgi` module based on :mod:`gevent.http`.
* Added evdns wrappers to :mod:`gevent.core` and DNS functions to :mod:`gevent.socket` module. Contributed by **Jason Toffaletti.**.
* Added a few a few options to ``setup.py`` to select a libevent library to compile against. Check them out with ``setup.py -h``.
* Added ``__all__`` to many modules that missed it.
* Converted the docstrings and the changelog to sphinx/rst markup.
* Added sphinx/rst documentation. It is available online at http://gevent.org.


Version 0.10.0
--------------

* Changed :class:`Timeout` API in a backward-incompatible way:
  :meth:`Timeout.__init__` does not start the timer immediately anymore;
  :meth:`Timeout.start` must be called explicitly.
  A shortcut - :meth:`Timeout.start_new` - is provided that creates and starts
  a :class:`Timeout`.
* Added :class:`gevent.Greenlet` class which is a subclass of greenlet that adds a few
  useful methods :meth:`join <Greenlet.join>`/:meth:`get <Greenlet.get>`/:meth:`kill <Greenlet.kill>`/:meth:`link <Greenlet.link>`.
* :func:`spawn` now returns :class:`Greenlet` instance. The old ``spawn``, which returns ``py.magic.greenlet``
  instance, can be still accessed as :meth:`spawn_raw`.

  .. note::

     The implementation of :class:`Greenlet` is an improvement on ``proc`` module, with these bugs fixed:

     * Proc was not a subclass of greenlet which makes :func:`getcurrent` useless and using
       Procs as keys in dict impossible.
     * Proc executes links sequentially, so one could block the rest from being
       executed. :class:`Greenlet` executes each link in a new greenlet by default, unless
       it is set up with :class:`Greenlet.rawlink` method.
     * Proc cannot be easily subclassed. To subclass :class:`Greenlet`, override its _run
       and __init__ methods.

* Added :class:`pool.Pool` class with the methods compatible to the standard :mod:`multiprocessing.pool`:
  :meth:`apply <Pool.apply>`, :meth:`map <Pool.map>` and others.
  It also has :meth:`spawn <Pool.spawn>` method which is always async and returns a
  :class:`Greenlet` instance.
* Added :mod:`gevent.event` module with 2 classes: :class:`Event` and :class:`AsyncResult`.
  :class:`Event` is a drop-in replacement for :class:`threading.Event`, supporting
  :meth:`set <Event.set>`/:meth:`wait <Event.wait>`/``get`` methods. :class:`AsyncResult`
  is an extension of :class:`Event` that supports exception passing via :meth:`set_exception <AsyncResult.set_exception>` method.
* Added :class:`queue.JoinableQueue` class with :meth:`task_done <queue.JoinableQueue.task_done>`
  and :meth:`join <queue.JoinableQueue.join>` methods.
* Renamed ``core.read`` and ``core.write`` classes to :class:`core.read_event` and :class:`core.write_event`.
* :mod:`gevent.pywsgi`: pulled **Mike Barton's** eventlet patches that fix double content-length issue.
* Fixed ``setup.py`` to search more places for system libevent installation.
  This fixes 64bit CentOS 5.3 installation issues, hopefully covers other platforms
  as well.

The following items were added to the gevent top level package:

- :func:`spawn_link`
- :func:`spawn_link_value`
- :func:`spawn_link_exception`
- :func:`spawn_raw`
- :func:`joinall`
- :func:`killall`
- :class:`Greenlet`
- :exc:`GreenletExit`
- :mod:`core`

The following items were marked as deprecated:

- gevent.proc module (:class:`wrap_errors` helper was moved to :mod:`util` module)
- gevent.coros.event
- gevent.coros.Queue and gevent.coros.Channel

Internally, ``gevent.greenlet`` was split into a number of modules:

- :mod:`gevent.hub` provides :class:`Hub` class and basic utilities, like :func:`sleep`;
  :class:`Hub` is now a subclass of greenlet.
- :mod:`gevent.timeout` provides :class:`Timeout` and :func:`with_timeout`
- :mod:`gevent.greenlet` provides :class:`Greenlet` class and helpers like :func:`joinall`
  and :func:`killall`.
- :mod:`gevent.rawgreenlet` contains the old "polling" versions of
  :func:`joinall <rawgreenlet.joinall>` and :func:`killall <rawgreenlet.killall>` (they do not need :meth:`link <Greenlet.link>`
  functionality and work with any greenlet by polling their status and sleeping in a loop)


Thanks to **Jason Toffaletti** for reporting the installation issue and providing a
test case for WSGI double content-length header bug.


Version 0.9.3
-------------

* Fixed all known bugs in the :mod:`gevent.queue` module made it 2.4-compatible.
  :class:`LifoQueue` and :class:`PriorityQueue` are implemented as well.
  :mod:`gevent.queue` will deprecate both ``coros.Queue`` and ``coros.Channel``.
* Fixed to :class:`Timeout` to raise itself by default. ``TimeoutError`` is gone.
  Silent timeout is now created by passing ``False`` instead of ``None``.
* Fixed bug in :func:`gevent.select.select` where it could silent the wrong timeout.
* :func:`spawn` and :func:`spawn_later` now avoid creating a closure and this decreases spawning
  time by 50%.
* ``kill``'s and ``killall``'s *wait* argument was renamed to *block*. The polling is now
  implemented by ``greenlet.join`` and ``greenlet.joinall`` functions and it become more
  responsive, with gradual increase of sleep time.
* Renamed ``proc.RunningProcSet`` to ``proc.ProcSet``.
* Added :func:`shutdown` function, which blocks until libevent has finished dispatching the events.
* The return value of ``event_add`` and ``event_del`` in core.pyx are now checked properly
  and :exc:`IOError` is raised if they have failed.
* Fixed backdoor.py, accidentally broken in the previous release.


Version 0.9.2
-------------

* Simplified :mod:`gevent.socket`'s implementation and fixed SSL
  bug reported on eventletdev by **Cesar Alaniz** as well as failures
  in test_socket_ssl.py.
* Removed ``GreenSocket.makeGreenFile``; Use :meth:`socket.socket.makefile` that returns _fileobject
  and is available on both :class:`GreenSocket <gevent.socket.socket>` and :class:`GreenSSL <gevent.socket.GreenSSL>`.
  socket.py still a work in progress.
* Added new :class:`core.active_event` class that takes advantage of libevent's event_active function.
  ``core.active_event(func)`` schedules func to be run in this event loop iteration as opposed
  to ``core.timer(0, ...)`` which schedules an event to be run in the next iteration.
  :class:`active_event` is now used throughout the library wherever ``core.timer(0, ....)`` was previously used.
  This results in :func:`spawn` being at least 20% faster compared to `Version 0.9.1`_ and twice as fast compared to
  eventlet. (The results are obtained with bench_spawn.py script in ``greentest/`` directory)
* Added boolean parameter *wait* to :func:`kill` and :func:`killall` functions. If set to ``True``, it makes the
  function block until the greenlet(s) is actually dead. By default, :func:`kill` and :func:`killall` are asynchronous,
  i.e. they don't unschedule the current greenlet.
* Added a few new properties to :class:`gevent.core.event`: :attr:`fd <event.fd>`, :attr:`events <event.events>`,
  :attr:`events_str <event.events_str>` and :attr:`flags <event.flags>`. It also has
  :meth:`__enter__ <event.__enter__>` and :meth:`__exit__ <event.__exit__>` now, so it can be used as a context manager. :class:`event`'s :attr:`callback <event.callback>` signature has changed from ``(event, fd, evtype)`` to ``(event, evtype)``.
* Fixed :class:`Hub`'s mainloop to never return successfully as this will screw up main greenlet's ``switch()`` call.
  Instead of returning it raises :class:`DispatchExit`.
* Added :func:`reinit` function - wrapper for libevent's ``event_reinit``.
  This function is a must have at least for daemons, as it fixes ``epoll`` and some others
  eventloops to work after ``fork``.
* Trying to use gevent in another thread will now raise an exception immediately,
  since it's not implemented.
* Added a few more convenience methods ``spawn_link[exception/value]`` to ``proc.RunningProcSet``.
* Fixed setup.py not to depend on setuptools.
* Removed ``gevent.timeout`` (use :class:`gevent.Timeout`)


Version 0.9.1
-------------

* Fixed compilation with gevent libevent-1.3 (Thanks to **Litao Wei** for reporting the problem.)
* Fixed :class:`Hub` to recover silently after ``event_dispatch()`` failures (I've seen this
  happen after ``fork`` even though ``event_reinit()`` is called as necessary). The end result is that :func:`fork`
  now works more reliably, as detected by ``test_socketserver.py`` - it used to fail occasionally, now it does not.
* Reorganized the package, most of the stuff from ``gevent/__init__.py`` was moved to ``gevent/greenlet.py``.
  ``gevent/__init__.py`` imports some of it back but not everything.
* Renamed ``gevent.timeout`` to :class:`gevent.Timeout`. The old name is available as an alias.
* Fixed a few bugs in :class:`queue.Queue`.
  Added test_queue.py from standard tests to check how good is :class:`queue.Queue` a replacement
  for a standard :mod:`Queue` (not good at all, timeouts in :meth:`queue.Queue.put` don't work yet)
* :mod:`monkey` now patches ssl module when on 2.6 (very limited support).
* Improved compatibility with Python 2.6 and Python 2.4.
* Greenlet installed from PyPI (without py.magic prefix) is properly recognized now.
* core.pyx was accidentally left out of the source package, it's included now.
* :class:`GreenSocket <socket.socket>` now wraps a ``socket`` object from ``_socket`` module rather
  than from :mod:`socket`.


Version 0.9.0
-------------

Started as eventlet_ 0.8.11 fork, with the intention to support only libevent as a backend.
Compared to eventlet, this version has a much simpler API and implementation and a few
severe bugs fixed, namely

* full duplex in sockets, i.e. ``read()`` and ``write()`` on the same fd do not cancel one another
* :meth:`GreenSocket.close <socket.socket.close>` does not hang as it could with eventlet
  (there's a test in my repo of eventlet that reproduces both of them:
  http://bitbucket.org/denis/eventlet/src/tip/greentest/test__socket.py)

Besides having less bugs and less code to care about the goals of the fork are:

* piggy-back on libevent as much as possible (use its http and dns code)
* use the interfaces and conventions from the standard Python library where possible

.. _eventlet: http://eventlet.net
