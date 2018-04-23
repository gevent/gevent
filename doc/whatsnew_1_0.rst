==========================
 What's new in gevent 1.0
==========================

.. toctree::
   :maxdepth: 2

   changelog_1_0


The detailed information is available in :doc:`changelog_1_0`. Below is the
summary of all changes since 0.13.8.

Gevent 1.0 supports Python 2.5 - 2.7. The version of greenlet required is 0.3.2. The source distribution
now includes the dependencies (libev and c-ares) and has no dependencies other than greenlet.


New core
========

Now the event loop is using libev instead of libevent (see http://blog.gevent.org/2011/04/28/libev-and-libevent/ for motivation).

The new :mod:`gevent.core` has been rewritten to wrap libev's API. (On Windows, the :mod:`gevent.core` accepts Windows handles
rather than stdio file descriptors.).

The signal handlers set with the standard signal module are no longer blocked by the event loop.

The event loops are now pluggable. The GEVENT_LOOP environment variable can specify the alternative class to use (the default is ``gevent.core.loop``).

The error handling is now done by Hub.handle_error().

The system errors that usually kill the process (SystemError, SystemExit, KeyboardInterrupt) are now re-raised in the main greenlet.
Thus ``sys.exit()`` when run inside a greenlet is no longer trapped and kills the process as expected.


New dns resolver
================

Two new DNS resolvers: threadpool-based one (enabled by default) and c-ares based one. That threadpool-based resolver was added mostly for Windows and Mac OS X platforms where c-ares might behave differently w.r.t system configuration. On Linux, however, the c-ares based resolver is probably a better choice. To enable c-ares resolver set GEVENT_RESOLVER=ares environment variable.

This fixes some major issues with DNS on 0.13.x, namely:

- Issue #2: DNS resolver no longer breaks after ``fork()``. You still need to call :func:`gevent.fork` (``os.fork`` is monkey patched with it if ``monkey.patch_all()`` was called).
- DNS resolver no longer ignores ``/etc/resolv.conf`` and ``/etc/hosts``.

The following functions were added to socket module:

- gethostbyname_ex
- getnameinfo
- gethostbyaddr
- getfqdn

It is possible to implement your own DNS resolver and make gevent use it. The GEVENT_RESOLVER variable can point to alternative implementation using the format: ``package.module.class``. The default is ``gevent.resolver_thread.Resolver``. The alternative "ares" resolver is an alias for ``gevent.resolver_ares.Resolver``.


New API
=======

- :func:`gevent.wait` and :func:`gevent.iwait`
- UDP server: gevent.server.DatagramServer
- Subprocess support

  New :mod:`gevent.subprocess` implements the interface of the standard subprocess module in a cooperative way.
  It is possible to monkey patch the standard subprocess module with ``patch_all(subprocess=True)`` (not done by default).

- Thread pool

  **Warning:** this feature is experimental and should be used with care.

  The :mod:`gevent.threadpool` module provides the usual pool methods (apply, map, imap, etc) but runs passed functions
  in a real OS thread.

  There's a default threadpool, available as ``gevent.get_hub().threadpool``.


Breaking changes
================

Removed features
----------------

- gevent.dns module (wrapper around libevent-dns)
- gevent.http module (wrapper around libevent-http)
- ``util.lazy_property`` property.
- deprecated gevent.sslold module
- deprecated gevent.rawgreenlet module
- deprecated name ``GreenletSet`` which used to be alias for :class:`Group`.
- link to greenlet feature of Greenlet
- undocumented bind_and_listen and tcp_listener

Renamed gevent.coros to gevent.lock. The gevent.coros is still available but deprecated.


API changes
-----------

In all servers, method "kill" was renamed to "close". The old name is available as deprecated alias.

- ``Queue(0)`` is now equivalent to an unbound queue and raises :exc:`DeprecationError`. Use :class:`gevent.queue.Channel` if you need a channel.

The :class:`gevent.Greenlet` objects:

- Added ``__nonzero__`` implementation that returns `True` after greenlet was started until it's dead. This overrides
  greenlet's __nonzero__ which returned `False` after `start()` until it was first switched to.


Bugfixes
========

- Issue #302: "python -m gevent.monkey" now sets __file__ properly.
- Issue #143: greenlet links are now executed in the order they were added
- Fixed monkey.patch_thread() to patch threading._DummyThread to avoid leak in threading._active.
- gevent.thread: allocate_lock is now an alias for LockType/Semaphore. That way it does not fail when being used as class member.
- It is now possible to add raw greenlets to the pool.
- The :meth:`map` and :meth:`imap` methods now start yielding the results as soon as possible.
- The :meth:`imap_unordered` no longer swallows an exception raised while iterating its argument.
- `gevent.sleep(<negative value>)` no longer raises an exception, instead it does `sleep(0)`.
- The :class:`WSGIServer` now sets `max_accept` to 1 if `wsgi.multiprocessing` is set to `True`.
- Added :func:`monkey.patch_module` function that monkey patches module using `__implements__` list provided by gevent module.
  All of gevent modules that replace stdlib module now have `__implements__` attribute.


pywsgi:

- Fix logging when bound on unix socket (#295).
- readout request data to prevent ECONNRESET
- Fix #79: Properly handle HTTP versions.
- Fix #86: bytearray is now supported.
- Fix #92: raise IOError on truncated POST requests.
- Fix #93: do not sent multiple "100 continue" responses
- Fix #116: Multiline HTTP headers are now handled properly.
- Fix #216: propagate errors raised by Pool.map/imap
- Fix #303: 'requestline' AttributeError in pywsgi.
- Raise an AssertionError if non-zero content-length is passed to start_response(204/304) or if non-empty body is attempted to be written for 304/204 response
- Made sure format_request() does not fail if 'status' attribute is not set yet
- Added REMOTE_PORT variable to the environment.
- Removed unused deprecated 'wfile' property from WSGIHandler
