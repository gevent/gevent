Changelog
=========

.. currentmodule:: gevent

Version 0.12.2
--------------

* Fixed http server to put the listening socket into a non-blocking mode. Contributed by **Ralf Schmitt**.


Version 0.12.1
--------------

* Removed a symlink from the distribution (that causes pip to fail). Thanks to **Brad Clements** for reporting it.
* setup.py: automatically create symlink from ``build/lib.../gevent/core.so`` to ``gevent/core.so``.
* :mod:`gevent.socket`: Improved compatibility with stdlib's socket:

  - Fixed :class:`socket <gevent.socket.socket>` to raise ``timeout("timed out")`` rather than simply ``timeout``.
  - Imported ``_GLOBAL_DEFAULT_TIMEOUT`` from standard :mod:`socket` module instead of creating a new object.


Version 0.12.0
--------------

- Release highlights:

  - Added :mod:`gevent.ssl` module.
  - Fixed Windows compatibility (experimental).
  - Improved performance of :meth:`socket.recv`, :meth:`socket.send` and similar methods.
  - Added a new module - :mod:`dns` - with synchronous wrappers around libevent's DNS API.
  - Added :class:`core.readwrite_event` and :func:`socket.wait_readwrite` functions.
  - Fixed several incompatibilities of :mod:`wsgi` module with the WSGI spec.
  - Deprecated :mod:`pywsgi` module.

- :mod:`gevent.wsgi` module

  - Made ``env["REMOTE_PORT"]`` into a string.
  - Fixed the server to close the iterator returned by the application.
  - Made ``wsgi.input`` object iterable.

- :mod:`gevent.core` module

  - Made DNS functions no longer accept/return IP addresses in dots-and-numbers format. They work
    with packed IPs now.
  - Made DNS functions no longer accept additional arguments to pass to the callback.
  - Fixed DNS functions to check the return value of the libevent functions and raise
    :exc:`IOError` if they failed.
  - Added :func:`core.dns_err_to_string`
  - Made core.event.cancel not to raise if event_del reports an error. instead, the return code is
    passed to the caller.
  - Fixed minor issue in string representation of the events.

- :mod:`gevent.socket` module

  - Fixed bug in socket.accept. It could return unwrapped socket instance if socket's timeout is 0.
  - Fixed socket.sendall implementation never to call underlying socket's sendall.
  - Fixed :func:`gethostbyname` and :func:`getaddrinfo` to call the stdlib if the passed hostname
    has no dots.
  - Fixed :func:`getaddrinfo` to filter the results using *socktype* and *proto* arguments.
  - Removed :func:`getnameinfo` as it didn't quite match the stdlib interface.
    Use :func:`dns.resolve_reverse` for reverse resolutions.
  - Fixed :meth:`socket.connect_ex` to use cooperative :func:`gethostbyname`.
  - Fixed :meth:`socket.dup` not to call underlying socket's :meth:`dup` (which is not available
    on Windows) but to use Python's reference counting similar to how the stdlib's socket
    implements :meth:`dup`
  - Added *_sock* argument to :class:`socket`'s constructor. Passing the socket instance
    as first argument is no longer supported.
  - Fixed :func:`socket.connect` to ignore ``WSAEINVAL`` on Windows.
  - Fixed :func:`socket.connect` to use :func:`wait_readwrite` instead of :func:`wait_write`.
  - Fixed :func:`socket.connect` to consult ``SO_ERROR``.
  - Fixed :func:`socket.send` and :func:`socket.sendall` to support *flags* argument.
  - Renamed :func:`socket_bind_and_listen` to :func:`socket.bind_and_listen`. The old name
    is still available as a deprecated alias.
  - The underlying socket object is now stored as ``_sock`` property.
  - Imported the constants and some utility functions from stdlib's :mod:`socket` into :mod:`gevent.socket`.
    (Thanks to **Matt Goodall** for the original patch).
  - Renamed :meth:`wrap_ssl` to :meth:`ssl`. (the old name is still available but deprecated)
  - Deprecated :func:`connect_tcp` and :func:`tcp_server`.
  - Added :exc:`sslerror` to ``socket.__all__``.
  - Removed :class:`GreenSocket` alias for socket class.
  - Moved PyOpenSSL-based implementation of :func:`socket.ssl` into :mod:`gevent.oldssl` module.
    It's imported into :mod:`gevent.socket` if importing :mod:`gevent.ssl` fails.

- Miscellaneous

  - Fixed Greenlet.spawn_link* and GreenletSet.spawn_link* classmethods not to assume anything
    about their arguments. (Thanks to **Marcus Cavanaugh** for pointing that out).
  - Fixed :func:`select <gevent.select.select>` to clean up properly if event creation fails.
  - Fixed :func:`select <gevent.select.select>` to raise :exc:`select.error` instead of :exc:`IOError`.
  - Fixed setup.py to proceed with compilation even if libevent version cannot be determined.
    1.x.x is assumed in this case.
  - Fixed compatibility of .pyx files with Cython 0.12.0
  - Renamed arguments for :func:`select.select` to what they are called in the stdlib
  - Removed internal function :func:`getLinkedCompleted` from :mod:`gevent.greenlet`
  - Remove ``#warning`` directives from ``libevent.h``. They are not supported by vc90.
  - Removed some deprecated stuff from :mod:`coros`.
  - Internal class :class:`Waiter <gevent.hub.Waiter>` now stores the value if no one's waiting for it.
  - Added ``testrunner.py`` script that replaces a bunch of small scripts that were used before.
  - Removed ``is_secure`` attribute from sockets and ssl objects.
  - Made Greenlet not to print a traceback when a not-yet-started greenlet is killed.
  - Added BackdoorServer class to backdoor module. Removed backdoor() function and deprecated backdoor_server() function.
  - Removed ``__getattr__`` from socket class.
  - Fixed :func:`monkey.patch_socket` not to fail if :func:`socket.ssl` is not present in :mod:`gevent.socket`.
  - Added :func:`monkey.patch_ssl`.
  - Added *aggressive* to :func:`monkey.patch_all`.
  - Tests from stdlib no longer included in greentest package. Instead, there are number of stubs
    that import those tests from ``test`` package directly and run them in monkey patched environment.
  - Added examples/process.py by **Marcus Cavanaugh**.


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
* Added sphinx/rst documentation. It is available online at http://www.gevent.org.


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

.. _eventlet: http://bitbucket.org/denis/eventlet
