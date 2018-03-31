===========================
 Changes before gevent 1.0
===========================

.. currentmodule:: gevent


Release 0.13.8 (September 6, 2012)
==================================

- Fixed :issue:`80`: gevent.httplib failed with RequestFailed errors because timeout was reset to 1s. Patch by Tomasz Prus.
- core: fix compilation with the latest Cython: remove emit_ifdef/emit_else/emit_endif.
- Fixed :issue:`132`: gevent.socket.gethostbyname(<unicode>) now does ascii encoding and uses gevent's resolver rather than calling built-in resolver. Patch by Alexey Borzenkov.


Release 0.13.7 (April 12, 2012)
===============================

- Fixed :issue:`94`: fallback to buffer if memoryview fails in _get_memory on python 2.7.
- Fixed :issue:`103`: ``Queue(None).full()`` returns ``False`` now (previously it returned ``True``).
- Fixed :issue:`112`: threading._sleep is not patched. Thanks to David LaBissoniere.
- Fixed :issue:`115`: _dummy gets unexpected Timeout arg.


Release 0.13.6 (May 2, 2011)
============================

- Added ``__copy__`` method to :class:`gevent.local.local` class that implements copy semantics compatible with built-in ``threading.local``. Patch by **Galfy Pundee**.
- Fixed :class:`StreamServer` class to catch ``EWOULDBLOCK`` rather than ``EAGAIN``. This fixes lots of spurious tracebacks on Windows where these two constants are not the same. Patch by **Alexey Borzenkov**.
- Fixed :issue:`65`: :func:`fork` now calls ``event_reinit`` only in the child process; otherwise the process could hang when using libevent2. Patch by **Alexander Boudkar**.


Release 0.13.5 (Apr 21, 2011)
=============================

- Fixed build problem on Python 2.5


Release 0.13.4 (Apr 11, 2011)
=============================

- Fixed :exc:`TypeError` that occurred when ``environ["wsgi.input"].read`` function was called with an integer argument.
- Fixed :issue:`63`: :func:`monkey.patch_thread` now patches :mod:`threading` too, even if it's already imported. Patch by **Shaun Lindsay**.
- Fixed :issue:`64`: :func:`joinall` and :func:`killall` functions used to hang if their argument contained duplicate greenlets.
- Fixed :issue:`69`: :class:`pywsgi.WSGIServer` reported "Connection reset by peer" if the client did not close the connection gracefully after the last request. Such errors are now ignored.
- Fixed :issue:`67`: Made :class:`wsgi.WSGIServer` add ``REQUEST_URI`` to environ. Patch by **Andreas Blixt**.
- Fixed :issue:`71`: monkey patching ``httplib`` with :mod:`gevent.httplib` used to break ``HTTPSConnection``. Patch by **Nick Barkas**.
- Fixed :issue:`74`: :func:`create_connection <gevent.socket.create_connection>` now raises proper exception when ``getaddrinfo`` fails.
- Fixed :meth:`BaseServer.__repr__` method, :attr:`BaseServer.server_host` and :attr:`BaseServer.server_port` attributes to handle the case of ``AF_UNIX`` addresses properly. Previously they assumed address is always a tuple.
- Fixed :class:`pywsgi.WSGIServer` to handle ``AF_UNIX`` listeners. The server now sets ``environ["SERVER_NAME"]`` and ``environ["SERVER_PORT"]`` to empty string in such case.
- Make :class:`StreamServer` (and thus :class:`pywsgi.WSGIServer`) accept up to 100 connections per one readiness notification. This behaviour is controlled by :attr:`StreamServer.max_accept` class attribute.
- If bind fails, the servers now include the address that caused bind to fail in the error message.


Release 0.13.3 (Feb 7, 2011)
============================

- Fixed typo in :mod:`gevent.httplib` that rendered it unusable.
- Removed unnecessary delay in :func:`getaddrinfo <gevent.socket.getaddrinfo>` by calling ``resolve_ipv4`` and ``resolve_ipv6`` concurrently rather than sequentially in ``AF_UNSPEC`` case.


Release 0.13.2 (Jan 28, 2011)
=============================

- Added :mod:`gevent.httplib` -- **experimental** support for libevent-http client (:issue:`9`). Thanks to **Tommie Gannert**, **Örjan Persson**.
- Fixed crash on Mac OS X (:issue:`31`). Patch by **Alexey Borzenkov**.
- Fixed compatiblity of :mod:`gevent.wsgi` with libevent2 (:issue:`62`).
- Fixed compilation issues with libevent2. Patch by **Ralf Schmitt**.
- Fixed :mod:`pywsgi` not to use chunked transfer encoding in case of 304 and 204 responses as it creates a non-empty message body which is against RFC and causes some browsers to fail. Patch by **Nicholas Piël**.
- Fixed :func:`socket.getaddrinfo` to handle ``AF_UNSPEC`` properly and resolve service names (:issue:`56`). Thanks to **Elizabeth Jennifer Myers**.
- Fixed :func:`socket.getaddrinfo` to handle international domain names.
- Fixed leaking of traceback object when switching out of greenlet with ``sys.exc_info`` set. Leaking is prevented by not preserving traceback at all and only keeping the value of the exception. Thanks to **Ned Rockson**.
- Fixed :meth:`ssl.SSLSocket.unwrap` to shutdown :class:`SSLSocket` properly, without raising ``SSLError(read operation timeout)``.
- Fixed :exc:`TypeError` inside :class:`Hub` on Python 2.4.
- Made a number of internal improvements to :mod:`gevent.pywsgi` to make subclassing easier.
- Changed :class:`WSGIServer <pywsgi.WSGIServer>` to explicitly close the socket after the last request. Patch by **Ralf Schmitt**.
- Fixed :class:`pywsgi.WSGIHandler` not to add ``CONTENT_TYPE`` to the *environ* dict when there's no ``Content-Type`` header in the request. Previously a default ``text/plain`` was added in such case.
- Added proper implementation of :meth:`imap_unordered <gevent.pool.Group.imap_unordered>` to :class:`Pool` class. Unlike previous "dummy" implementation this one starts yielding the results as soon as they are ready.
- Implemented iterator protocol in :class:`Queue <gevent.queue.Queue>`. The main use case is the implementation of :meth:`Pool.imap_unordered`.
- Fixed :attr:`BaseServer.started` property: it is now set to ``True`` after :meth:`start <StreamServer.start>` until :meth:`stop <StreamServer.stop>` or :meth:`kill <StreamServer.kill>`. Previously it could become ``False`` for short period of times, because :class:`StreamServer` could stop accepting for a while in presence of errors and :attr:`StreamServer.started` was defined as "whether the server is currently accepting".
- Fixed :class:`wsgi.WSGIServer` to reply with 500 error immediately if the application raises an error (:issue:`58`). Thanks to **Jon Aslund**.
- Added :func:`monkey.patch_httplib` function which is disabled by default.
- Added *httplib* parameter to :func:`monkey.patch_all` (defaults to ``False``).
- Added :func:`write <core.buffer.write>` method to :class:`core.buffer`.
- Fixed :exc:`OverflowError` that could happen in :meth:`core.event.__str__`.
- Made :meth:`http_request.get_input_headers` return header names in lower case.
- Fixed :class:`StreamServer` to accept *ciphers* as an SSL argument.
- Added ``build_exc --cython=`` option to ``setup.py``. Patch by **Ralf Schmitt**.
- Updated :class:`local <gevent.local.local>` to raise :exc:`AttributeError` if ``__dict__`` attribute is set or deleted.


Release 0.13.1 (Sep 23, 2010)
=============================

Release highlights:

- Fixed :mod:`monkey` to patch :func:`socket.create_connection <gevent.socket.create_connection>`.
- Updated :mod:`gevent.ssl` module to fully match the functionality of :mod:`ssl` on Python 2.7.
- Fixed :meth:`Group.join` to handle ``raise_error=True`` properly, it used to raise :exc:`TypeError` (:issue:`36`). Thanks to by **David Hain**.
- Fixed :mod:`gevent.wsgi` and :mod:`gevent.pywsgi` to join multiple ``Cookie`` headers (:issue:`40`).
- Fixed :func:`select <gevent.select.select>` to recognize ``long`` arguments in addition to ``int``.
- Fixed :meth:`Semaphore.acquire` to return ``False`` when timeout expires instead of raising :exc:`AssertionError` (:issue:`39`). Patch by **Erik Näslund**.
- Fixed :meth:`JoinableQueue.join` to return immediately if queue is already empty (:issue:`45`). Patch by **Dmitry Chechik**.
- Deprecated :mod:`gevent.sslold` module.

:mod:`gevent.socket` module:

- Overrode :meth:`socket.shutdown` method to interrupt read/write operations on socket.
- Fixed possible :exc:`NameError` in :meth:`socket.connect_ex` method. Patch by **Alexey Borzenkov**.
- Fixed socket leak in :func:`create_connection` function.
- Made :mod:`gevent.socket` import all public items from stdlib :mod:`socket` that do not do I/O.

:mod:`gevent.ssl` module:

- Imported a number of patches from stdlib by **Antoine Pitrou**:

  - Calling :meth:`makefile` method on an SSL object would prevent the underlying socket from being closed until all objects get truly destroyed (Python issue #5238).
  - SSL handshake would ignore the socket timeout and block indefinitely if the other end didn't respond (Python issue #5103).
  - When calling :meth:`getpeername` in ``SSLSocket.__init__``, only silence exceptions caused by the "socket not connected" condition.

- Added support for *ciphers* argument.
- Updated ``SSLSocket.send`` and ``SSLSocket.recv`` methods to match the behavior of stdlib :mod:`ssl` better.
- Fixed :class:`ssl.SSLObject` to delete events used by other greenlets when closing the instance (:issue:`34`).

Miscellaneous:

- Made :class:`BaseServer` accept ``long`` values as *pool* argument in addition to ``int``.
- Made :attr:`http._requests` attribute public.
- Updated webchat example to use file on disk rather than in-memory sqlite database to avoid :exc:`OperationalError`.
- Fixed ``webproxy.py`` example to be runnable under external WSGI server.
- Fixed bogus failure in ``test__exc_info.py``.
- Added new test to check PEP8 conformance: ``xtest_pep8.py``.
- Fixed :class:`BackdoorServer` close the connection on :exc:`SystemExit` and simplified the code.
- Made :class:`Pool` raise :exc:`ValueError` when initialized with ``size=0``.
- Updated ``setup.py --libevent`` to configure and make libevent if it's not built already.
- Updated ``setup.py`` to use ``setuptools`` if present and add dependency on ``greenlet``.
- Fixed doc/mysphinxext.py to work with Sphinx 1. Thanks by **Örjan Persson**.


Release 0.13.0 (Jul 14, 2010)
=============================

Release highlights:

- Added :mod:`gevent.server` module with :class:`StreamServer` class for easy implementing of TCP and SSL servers.
- Added :mod:`gevent.baseserver` module with :class:`BaseServer` class.
- Added new implementation of :mod:`gevent.pywsgi` based on :mod:`gevent.server`. Contributed by **Ralf Schmitt**.
- Added :mod:`gevent.local` module. Fixed :issue:`24`. Thanks to **Ted Suzman**.
- Fixed a number of bugs in :mod:`gevent.wsgi` module.
- Fixed :issue:`26`: closing a socket now interrupts all pending read/write operations on it.
- Implemented workaround that prevents greenlets from leaking ``exc_info``.
- Fixed :meth:`socket.sendall` to use buffer object to prevent string copies.
- Made the interfaces of :mod:`gevent.wsgi` and :mod:`gevent.pywsgi` much more similar to each other.
- Fixed compilation on Windows with libevent-2.
- Improved Windows compatibility. Fixed :issue:`30`. Thanks to **Luigi Pugnetti**.
- Fixed compatibility with Python 2.7.

Backward-incompatible changes:

- Blocking is now the default behaviour for the :meth:`Greenlet.kill` method and other kill* methods.
- Changed the inteface of :class:`http.HTTPServer` to match the interface of other servers.
- Changed :class:`Pool`'s :meth:`spawn` method to block until there's a free slot.
- Removed deprecated :func:`backdoor.backdoor_server` function.
- Removed deprecated functions in :mod:`socket` module:

  - :func:`socket_bind_and_listen`
  - :func:`set_reuse_addr`
  - :func:`connect_tcp`
  - :func:`tcp_server`

- Removed deprecated :attr:`socket.fd` property.
- Deprecated use of negative numbers to indicate infinite timeout in :func:`core.event.add` and :func:`socket.wait_read` and similar. Use ``None`` from now on, which is compatible with the previous versions.
- Derived :class:`backdoor.BackdoorServer` from :class:`StreamServer` rather than from :class:`Greenlet`. This adds lots of new features and removes a few old ones.
- Removed non-standard :attr:`balance` property from :class:`Semaphore`.
- Removed :func:`start`, :func:`set_cb` and :func:`set_gencb` from :class:`core.http`.
- Removed :func:`set_closecb` from :class:`core.http_connection`. It is now used internally to detach the requests of the closed connections.
- Deprecated :mod:`rawgreenlet` module.
- Deprecated :func:`util.lazy_property`.
- Renamed :class:`GreenletSet` to :class:`Group`. The old name is currently available as an alias.

:mod:`gevent.socket` module:

- Fixed issues :issue:`26` and :issue:`34`: closing the socket while reading/writing/connecting is now safe. Thanks to **Cyril Bay**.
- Imported :func:`getfqdn` from :mod:`socket` module.
- The module now uses ``sys.platform`` to detect Windows rather than :mod:`platform` module.
- Fixed :issue:`27`: :func:`getaddrinfo` used to handle the case when *socktype* or *proto* were equal to ``0``. Thanks to **Randall Leeds**.

:mod:`gevent.coros` module:

- Added :class:`RLock` class.
- Added :class:`DummySemaphore` class.
- Fixed :class:`BoundedSemaphore` class to behave like :class:`threading.BoundedSemaphore` behaves.

:mod:`gevent.event` module:

- Made :meth:`Event.wait` return internal flag instead of ``None``.
- Made :meth:`AsyncResult.wait` return its ``value`` instead of ``None``.
- Added :meth:`ready` method as an alias for :meth:`is_set`.

:mod:`gevent.wsgi` module:

- Removed :class:`wsgi.buffer_proxy`.

:mod:`gevent.pywsgi` module:

- Rewritten to use :mod:`server` and not to depend on :mod:`BaseHTTPServer`.
- Changed the interface to match :mod:`wsgi` module.
  Removed :func:`server` function, add :class:`Server` class, added :class:`WSGIServer` class.
- Renamed :class:`HttpProtocol` to :class:`WSGIHandler`.
- Fixed compatibility with webob by allowing an optional argument to :meth:`readline`.

:mod:`gevent.core` module:

- Fixed reference leaks in :class:`event` class.
- Avoid Python name lookups when accessing EV_* constants from Cython code. Patch by **Daniele Varrazzo**.
- Added *persist* argument to :class:`read_event`, :class:`write_event` and :class:`readwrite_event`.
- Made all of the event loop callbacks clear the exception info before exiting.
- Added :attr:`flags_str` property to :class:`event`. It is used by ``__str__`` and ``__repr__``.
- :class:`buffer <core.buffer>`:

  - Added :meth:`detach` method.
  - Implemented iterator protocol.
  - Fixed :meth:`readline` and :meth:`readlines` methods.

- :class:`http_request`:

  - Fixed :meth:`detach` to detach input and output buffers too.
  - Changed the response to send 500 error upon deallocation, if no response was sent by the user.
  - Made :attr:`input_buffer` and :attr:`output_buffer` store and reuse the :class:`buffer` object they create.
  - Fixed :meth:`__str__` and meth:`__repr__` to include spaces where needed.
  - :class:`http` class no longer has :meth:`set_cb` and :meth:`set_gencb`. Instead its contructor accepts *handle* which will be called on each request.

:mod:`gevent.http` and :mod:`gevent.wsgi` modules:

- Made :class:`HTTPServer` use ``"Connection: close"`` header by default.
- Class :class:`HTTPServer` now derives from :class:`baseserver.BaseServer`. Thus its :meth:`start` method no longer accepts socket to listen on, it must be passed to the contructor.
- The *spawn* argument now accepts a :class:`Pool` instance. While the pool is full, the server replies with 503 error.
- The server no longer links to the greenlets it spawns to detect errors. Instead, it relies on :class:`http_request` which will send 500 reply when deallocated if the user hasn't send any.

Miscellaneous:

- Changed :mod:`gevent.thread` to use :class:`Greenlet` instead of raw greenlets. This means monkey patched thread will become :class:`Greenlet` too.
- Added :attr:`started` property to :class:`Greenlet`.
- Put common server code in :mod:`gevent.baseserver` module. All servers in gevent package are now derived from :class:`BaseServer`.
- Fixed :issue:`20`: :func:`sleep` now raises :exc:`IOError` if passed a negative argument.
- Remove the code related to finding out libevent version from setup.py as macro ``USE_LIBEVENT_?`` is no longer needed to build ``gevent.core``.
- Increased default backlog in all servers (from 5 to 256). Thanks to **Nicholas Piël**.
- Fixed doc/conf.py to work in Python older than 2.6. Thanks to **Örjan Persson**.
- Silenced SystemError raised in :mod:`backdoor` when a client typed ``quit()``.
- If importing :mod:`greenlet` failed with ImportError, keep the original error message,
  because sometimes the error originates in setuptools.
- Changed :func:`select.select` to return all the file descriptors signalled, not just the first one.
- Made :mod:`thread` (and thus monkey patched threads) to spawn :class:`Greenlet` instances, rather than raw greenlets.

Examples:

- Updated echoserver.py to use :class:`StreamServer`.
- Added geventsendfile.py.
- Added wsgiserver_ssl.py.

Thanks to **Ralf Schmitt** for :mod:`pywsgi`, a number of fixes for :mod:`wsgi`, help with
:mod:`baseserver` and :mod:`server` modules, improving setup.py and various other patches and suggestions.

Thanks to **Uriel Katz** for :mod:`pywsgi` patches.


Release 0.12.2 (Mar 2, 2010)
============================

* Fixed http server to put the listening socket into a non-blocking mode. Contributed by **Ralf Schmitt**.


Release 0.12.1 (Feb 26, 2010)
=============================

* Removed a symlink from the distribution (that causes pip to fail). Thanks to **Brad Clements** for reporting it.
* setup.py: automatically create symlink from ``build/lib.../gevent/core.so`` to ``gevent/core.so``.
* :mod:`gevent.socket`: Improved compatibility with stdlib's socket:

  - Fixed :class:`socket <gevent.socket.socket>` to raise ``timeout("timed out")`` rather than simply ``timeout``.
  - Imported ``_GLOBAL_DEFAULT_TIMEOUT`` from standard :mod:`socket` module instead of creating a new object.


Release 0.12.0 (Feb 5, 2010)
============================

Release highlights:

- Added :mod:`gevent.ssl` module.
- Fixed Windows compatibility (experimental).
- Improved performance of :meth:`socket.recv`, :meth:`socket.send` and similar methods.
- Added a new module - :mod:`dns` - with synchronous wrappers around libevent's DNS API.
- Added :class:`core.readwrite_event` and :func:`socket.wait_readwrite` functions.
- Fixed several incompatibilities of :mod:`wsgi` module with the WSGI spec.
- Deprecated :mod:`pywsgi` module.

:mod:`gevent.wsgi` module:

- Made ``env["REMOTE_PORT"]`` into a string.
- Fixed the server to close the iterator returned by the application.
- Made ``wsgi.input`` object iterable.

:mod:`gevent.core` module:

- Made DNS functions no longer accept/return IP addresses in dots-and-numbers format. They work
  with packed IPs now.
- Made DNS functions no longer accept additional arguments to pass to the callback.
- Fixed DNS functions to check the return value of the libevent functions and raise
  :exc:`IOError` if they failed.
- Added :func:`core.dns_err_to_string`.
- Made core.event.cancel not to raise if event_del reports an error. instead, the return code is
  passed to the caller.
- Fixed minor issue in string representation of the events.

:mod:`gevent.socket` module:

- Fixed bug in socket.accept. It could return unwrapped socket instance if socket's timeout is 0.
- Fixed socket.sendall implementation never to call underlying socket's sendall.
- Fixed :func:`gethostbyname` and :func:`getaddrinfo` to call the stdlib if the passed hostname has no dots.
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

Miscellaneous:

- Fixed Greenlet.spawn_link* and GreenletSet.spawn_link* classmethods not to assume anything
  about their arguments. (Thanks to **Marcus Cavanaugh** for pointing that out).
- Fixed :func:`select <gevent.select.select>` to clean up properly if event creation fails.
- Fixed :func:`select <gevent.select.select>` to raise :exc:`select.error` instead of :exc:`IOError`.
- Fixed setup.py to proceed with compilation even if libevent version cannot be determined.
  1.x.x is assumed in this case.
- Fixed compatibility of .pyx files with Cython 0.12.0.
- Renamed arguments for :func:`select.select` to what they are called in the stdlib.
- Removed internal function :func:`getLinkedCompleted` from :mod:`gevent.greenlet`.
- Remove ``#warning`` directives from ``libevent.h``. They are not supported by vc90.
- Removed some deprecated stuff from :mod:`coros`.
- Internal class :class:`Waiter <gevent.hub.Waiter>` now stores the value if no one's waiting for it.
- Added ``testrunner.py`` script that replaces a bunch of small scripts that were used before.
- Removed ``is_secure`` attribute from sockets and ssl objects.
- Made :class:`Greenlet` not to print a traceback when a not-yet-started greenlet is killed.
- Added :class:`BackdoorServer` class to :mod:`backdoor`. Removed :func:`backdoor` function and deprecated :func:`backdoor_server` function.
- Removed ``__getattr__`` from socket class.
- Fixed :func:`monkey.patch_socket` not to fail if :func:`socket.ssl` is not present in :mod:`gevent.socket`.
- Added :func:`monkey.patch_ssl`.
- Added *aggressive* argument to :func:`monkey.patch_all`.
- Tests from stdlib no longer included in greentest package. Instead, there are number of stubs
  that import those tests from ``test`` package directly and run them in monkey patched environment.
- Added examples/process.py by **Marcus Cavanaugh**.


Release 0.11.2 (Dec 10, 2009)
=============================

* Fixed :mod:`wsgi` to unquote ``environ['PATH_INFO']`` before passing to application.
* Added ``SERVER_SOFTWARE`` variable to :mod:`wsgi` environ.
* Fixed bug in :meth:`JoinableQueue.task_done` that caused :class:`ValueError` to be raised incorrectly here.
* Fixed :mod:`gevent.socket` not to fail with :class:`ImportError` if Python was not built with ssl support.


Release 0.11.1 (Nov 15, 2009)
=============================

* Fixed bug in :func:`select.select` function. Passing non-empty list of write descriptors used to cause this function to fail.
* Changed setup.py to go ahead with the compilation even if the actual version of libevent cannot be determined (version 1.x.x is assumed in that case).

Contributed by **Ludvig Ericson**:

* Fixed :mod:`wsgi`'s ``start_response`` to recognize *exc_info* argument.
* Fixed setup.py to look for libevent.dylib rather than .so on Darwin platforms.


Release 0.11.0 (Oct 9, 2009)
============================

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


Release 0.10.0 (Aug 26, 2009)
=============================

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
- :mod:`gevent.timeout` provides :class:`Timeout` and :func:`with_timeout`;
- :mod:`gevent.greenlet` provides :class:`Greenlet` class and helpers like :func:`joinall` and :func:`killall`.
- :mod:`gevent.rawgreenlet` contains the old "polling" versions of
  :func:`joinall <rawgreenlet.joinall>` and :func:`killall <rawgreenlet.killall>` (they do not need :meth:`link <Greenlet.link>`
  functionality and work with any greenlet by polling their status and sleeping in a loop)


Thanks to **Jason Toffaletti** for reporting the installation issue and providing a
test case for WSGI double content-length header bug.


Release 0.9.3 (Aug 3, 2009)
===========================

* Fixed all known bugs in the :mod:`gevent.queue` module and made it 2.4-compatible.
  :class:`LifoQueue` and :class:`PriorityQueue` are implemented as well.
  :mod:`gevent.queue` will deprecate both ``coros.Queue`` and ``coros.Channel``.
* Fixed :class:`Timeout` to raise itself by default. ``TimeoutError`` is gone.
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


Release 0.9.2 (Jul 20, 2009)
============================

* Simplified :mod:`gevent.socket`'s implementation and fixed SSL bug reported on eventletdev
  by **Cesar Alaniz** as well as failures in ``test_socket_ssl.py``.
* Removed ``GreenSocket.makeGreenFile``; Use :meth:`socket.socket.makefile` that returns :class:`_fileobject`
  and is available on both :class:`GreenSocket <gevent.socket.socket>` and :class:`GreenSSL <gevent.socket.GreenSSL>`.
  The :mod:`gevent.socket` is still a work in progress.
* Added new :class:`core.active_event` class that takes advantage of libevent's ``event_active`` function.
  ``core.active_event(func)`` schedules func to be run in this event loop iteration as opposed
  to ``core.timer(0, ...)`` which schedules an event to be run in the next iteration.
  :class:`active_event` is now used throughout the library wherever ``core.timer(0, ....)`` was previously used.
  This results in :func:`spawn` being at least 20% faster compared to release 0.9.1 and twice as fast compared to
  eventlet. (The results are obtained with bench_spawn.py script in ``greentest/`` directory)
* Added boolean parameter *wait* to :func:`kill` and :func:`killall` functions. If set to ``True``, it makes the
  function block until the greenlet(s) is actually dead. By default, :func:`kill` and :func:`killall` are asynchronous,
  i.e. they don't unschedule the current greenlet.
* Added a few new properties to :class:`gevent.core.event`: :attr:`fd <event.fd>`, :attr:`events <event.events>`,
  :attr:`events_str <event.events_str>` and :attr:`flags <event.flags>`. It also has :meth:`__enter__ <event.__enter__>`
  and :meth:`__exit__ <event.__exit__>` now, so it can be used as a context
  manager. :class:`event`'s :attr:`callback <event.callback>` signature has changed from ``(event, fd, evtype)`` to ``(event, evtype)``.
* Fixed :class:`Hub`'s mainloop to never return successfully as this will screw up main greenlet's ``switch()`` call.
  Instead of returning it raises ``DispatchExit``.
* Added :func:`reinit` function - wrapper for libevent's ``event_reinit``.
  This function is a must have at least for daemons, as it fixes ``epoll`` and some others eventloops to work after ``fork``.
* Trying to use gevent in another thread will now raise an exception immediately, since it's not implemented.
* Added a few more convenience methods ``spawn_link[exception/value]`` to ``proc.RunningProcSet``.
* Fixed ``setup.py`` not to depend on ``setuptools``.
* Removed ``gevent.timeout``. Use :class:`gevent.Timeout`.


Release 0.9.1 (Jul 9, 2009)
===========================

* Fixed compilation with libevent-1.3. Thanks to **Litao Wei** for reporting the problem.
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


Release 0.9.0 (Jul 8, 2009)
===========================

Started as eventlet_ 0.8.11 fork, with the intention to support only libevent as a backend.
Compared to eventlet, this version has a much simpler API and implementation and a few
severe bugs fixed, namely

* Full duplex in sockets, i.e. ``read()`` and ``write()`` on the same fd do not cancel one another.
* The :meth:`GreenSocket.close <socket.socket.close>` method does not hang as it could with eventlet.

There's a test in my repo of eventlet that reproduces both of them:
http://bitbucket.org/denis/eventlet/src/tip/greentest/test__socket.py

Besides having less bugs and less code to care about the goals of the fork are:

* Piggy-back on libevent as much as possible (use its http and dns code).
* Use the interfaces and conventions from the standard Python library where possible.

.. _eventlet: http://bitbucket.org/denis/eventlet
