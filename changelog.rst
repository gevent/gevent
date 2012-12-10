Changelog
=========

.. currentmodule:: gevent


Release 1.0rc2
--------------

- Fixed #210: callbacks were not run for non-default loop (bug introduced in 1.0rc1).
- patch_all() no longer patches subprocess unless `subprocess=True` is passed.
- Fixed AttributeError in hub.Waiter.
- Fixed #181: make hidden imports visible to freezing tools like py2exe. Patch by Ralf Schmitt.
- Fixed #202: periodically yield when running callbacks (sleep(0) cannot block the event loop now).
- Fixed #204: os.tp_read/tp_write did not propogate errors to the caller.
- Fixed #217: do not set SO_REUSEADDR on Windows.
- Fixed bug in --module argument for gevent.monkey. Patch by Örjan Persson.
- Remove warning from threadpool.py about mixing fork() and threads.
- Cleaned up hub.py from code that was needed to support older greenlets. Patch by Saúl Ibarra Corretgé.
- Allow for explicit default loop creation via `get_hub(default=True)`. Patch by Jan-Philip Gehrcke.


Release 1.0rc1
--------------

- Fixed hub.switch() not to touch stacktrace when switching. greenlet restores the exception information correctly since version 0.3.2. gevent now requires greenlet >= 0.3.2
- Added gevent.wait() and gevent.iwait(). This is like gevent.joinall() but supports more objects, including Greenlet, Event, Semaphore, Popen. Without arguments it waits for the event loop to finish (previously gevent.run() did that). gevent.run will be removed before final release and gevent.joinall() might be deprecated.
- Reimplemented loop.run_callback with a list and a single prepare watcher; this fixes the order of spawns and improves performance a little.
- Fixes Semaphore/Lock not to init hub in `__init__`, so that it's possible to have module-global locks without initializing the hub. This fixes monkey.patch_all() not to init the hub.
- New implementation of callbacks that executes them in the order they were added. core.loop.callback is removed.
- Fixed 2.5 compatibility.
- Fixed crash on Windows when request 'prev' and 'attr' attributes of 'stat' watcher. The attribute access still fails, but now with an exception.
- Added known_failures.txt that lists all the tests that fail. It can be used by testrunner.py via expected option. It's used when running the test suite in travis.
- Fixed socket, ssl and fileobject to not mask EBADF error - it is now propogated to the caller. Previously EBADF was converted to empty read/write. Thanks to Vitaly Kruglikov
- Removed gevent.event.waitall()
- Renamed FileObjectThreadPool -> FileObjectThread
- Greenlet: Fixed #143: greenlet links are now executed in the order they were added
- Synchronize access to FileObjectThread with Semaphore
- EINVAL is not longer handled in fileobject.

monkey:

- Fixed #178: disable monkey patch os.read/os.write
- Fixed monkey.patch_thread() to patch threading._DummyThread to avoid leak in threading._active. Original patch by Wil Tan.
- added Event=False argument to patch_all() and patch_thread
- added patch_sys() which patches stdin, stdout, stderr with FileObjectThread wrappers. Experimental / buggy.
- monkey patching everything no longer initializes the hub/event loop.

socket:

- create_connection: do not lookup IPv6 address if IPv6 is unsupported. Patch by Ralf Schmitt.

pywsgi:

- Fixed #86: bytearray is now supported. Original patch by Aaron Westendorf.
- Fixed #116: Multiline HTTP headers are now handled properly. Patch by Ralf Schmitt.

subprocess:

- Fixed Windows compatibility. The wait() method now also supports 'timeout' argument on Windows.
- Popen: Added rawlink() method, which makes Popen objects supported by gevent.wait(). Updated examples/processes.py
- Fixed #148: read from errpipe_read in small chunks, to avoid trigger EINVAL issue on Mac OS X. Patch by Vitaly Kruglikov
- Do os._exit() in "finally" section to avoid executing unrelated code. Patch by Vitaly Kruglikov.

resolver_ares:

- improve getaddrinfo: For string ports (e.g. "http") resolver_ares/getaddrinfo previously only checked either getservbyname(port, "tcp") or getservbyname(port, "udp"), but never both. It now checks both of them.
- gevent.ares.channel now accepts strings as arguments
- upgraded c-ares to cares-1_9_1-12-g805c736
- it is not possible to configure resolver_ares directly with environ, like GEVENTARES_SERVERS

os:

- Renamed threadpool_read/write to tp_read/write.
- Removed posix_read, posix_write.
- Added nb_read, nb_write, make_nonblocking.

hub:

- The system error is now raised immediatelly in main greenlet in all cases.
- Dropped support for old greenlet versions (need >= 0.3.2 now)

core:

- allow 'callback' property of watcher to be set to None. "del w.callback" no longer works.
- added missing 'noinotify' flag

Misc:

- gevent.thread: allocate_lock is now an alias for LockType/Semaphore. That way it does not fail when being used as class member.
- Updated greentest.py to start timeouts with `ref=False`.
- pool: remove unused get_values() function
- setup.py now recognizes GEVENTSETUP_EV_VERIFY env var which sets EV_VERIFY macro when compiling
- Added a few micro benchmarks
- stdlib tests that we care about are now included in greentest/2.x directories, so we don't depend on them being installed system-wide
- updated util/makedist.py
- the testrunner was completely rewritten.


Release 1.0b4
-------------

- Added gevent.os module with 'read' and 'write' functions. Patch by Geert Jansen.
- Moved gevent.hub.fork to gevent.os module (it is still available as gevent.fork).
- Fixed issue #148: Made fileobject handle EINVAL, which is randomly raised by os.read/os.write on Mac OS X. Thanks to Mark Hingston.
- Fixed issue #150: gevent.fileobject.SocketAdapter.sendall() could needlessly wait for write event on the descriptor. Original patch by Mark Hingston.
- Fixed AttributeError in baseserver. In case of error, start() would call kill() which was renamed to close(). Thanks to Vitaly Kruglikov.


Release 1.0b3
-------------

- New gevent.subprocess module
- New gevent.fileobject module
- Fixed ThreadPool to discard references of the objects passed to it (function, arguments) asap. Previously they could be stored for unlimited time until the thread gets a new job.
- Fixed #138: gevent.pool.Pool().imap_unordered hangs with an empty iterator. Thanks to exproxus.
- Fixed #127: ssl.py could raise TypeError in certain cases. Thanks to Johan Mjones.
- Fixed socket.makefile() to keep the timeout setting of the socket instance. Thanks to Colin Marc.
- Added 'copy()' method to queues.
- The 'nochild' event loop config option is removed. The install_sigchld offer more flexible way of enabling child watchers.
- core: all watchers except for 'child' now accept new 'priority' keyword argument
- gevent.Timeout accepts new arguments: 'ref' and 'priority'. The default priority for Timeout is -1.
- Hub.wait() uses Waiter now instead of raw switching
- Updated libev to the latest CVS version
- Made pywsgi to raise an AssertionError if non-zero content-length is passed to start_response(204/304) or if non-empty body is attempted to be written for 304/204 response
- Removed pywsgi feature to capitalize the passed headers.
- Fixed util/cythonpp.py to work on python3.2 (#123). Patch by Alexandre Kandalintsev.
- Added 'closed' readonly property to socket.
- Added 'ref' read/write property to socket.
- setup.py now parses CARES_EMBED and LIBEV_EMBED parameters, in addition to EMBED.
- gevent.reinit() and gevent.fork() only reinit hub if it was created and do not create it themselves
- Fixed setup.py not to add libev and c-ares to include dirs in non-embed mode. Patch by Ralf Schmitt.
- Renamed util/make_dist.py to util/makedist.py
- testrunner.py now saves more information about the system; the stat printing functionality is moved to a separate util/stat.py script.


Release 1.0b2
-------------

Major and backward-incompatible changes:

- Made the threadpool-based resolver the default. To enable the ares-based resolver, set GEVENT_RESOLVER=ares env var.
- Added support for child watchers (not available on Windows).
  - Libev loop now reaps all children by default.
  - If NOCHILD flag is passed to the loop, child watchers and child reaping are disabled.
- Renamed gevent.coros to gevent.lock. The gevent.coros is still available but deprecated.
- Added 'stat' watchers to loop.
- The setup.py now recognizes gevent_embed env var. When set to "no", bundled c-ares and libev are ignored.
- Added optional 'ref' argument to sleep(). When ref=false, the watchers created by sleep() do not hold gevent.run() from exiting.
- ThreadPool now calls Hub.handle_error for exceptions in worker threads.
- ThreadPool got new method: apply_e.
- Added new extension module gevent._util and moved gevent.core.set_exc_info function there.
- Added new extension module gevent._semaphore. It contains Semaphore class which is imported by gevent.lock as gevent.lock.Semaphore. Providing Semaphore in extension module ensures that trace function set with settrace will not be called during __exit__. Thanks to Ralf Schmitt.
- It is now possible to kill or pre-spawn threads in ThreadPool by setting its 'size' property.

core:

- Make sure the default loop cannot be destroyed more than once, thus crashing the process.
- Make Hub.destroy() method not to destroy the default loop, unless *destroy_loop* is *True*. Non-default loops are still destroyed by default.
- loop: Removed properties from loop: fdchangecnt, timercnt, asynccnt.
- loop: Added properties: sigfd, origflags, origflags_int
- loop: The EVFLAG_NOENV is now always passed to libev. Thus LIBEV_FLAGS env variable is no longer checked. Use GEVENT_BACKEND.

Misc:

- Check that the argument of link() is callable. Raise TypeError when it's not.
- Fixed TypeError in baseserver when parsing an address.
- Pool: made add() and discard() usable by external users. Thanks to Danil Eremeev.
- When specifying a class to import, it is not possible to use format path/package.module.name
- pywsgi: Made sure format_request() does not fail if 'status' attribute is not set yet
- pywsgi: Added REMOTE_PORT variable to the environment.

Examples:

- portforwarder.py now shows how to use gevent.run() to implement graceful shutdown of a server.
- psycopg2_pool.py: Changed execute() to return rowcount.
- psycopg2_pool.py: Added fetchall() and fetchiter() methods.

Developer utilities:

- When building, CYTHON env variable can be used to specify Cython executable to use.
- util/make_dist.py now recongizes --fast and --revert options. Previous --rsync option is removed.
- Added util/winvbox.py which automates building/testing/making binaries on Windows VM.
- Fixed typos in exception handling code in testrunner.py
- Fixed patching unittest.runner on Python2.7. This caused the details of test cases run lost.
- Made testrunner.py kill the whole process group after test is done.


Release 1.0b1
-------------

Backward-incompatible changes:

- Removed "link to greenlet" feature of Greenlet.
- If greenlet module older than 0.3.2 is used, then greenlet.GreenletExit.__bases__ is monkey patched to derive from BaseException and not Exception. That way gevent.GreenletExit is always derived from BaseException, regardless of installed greenlet version.
- Some code supporting Python 2.4 has been removed.

Release highlights:

- Added thread pool: gevent.threadpool.ThreadPool.
- Added thread pool-based resolver. Enable with GEVENT_RESOLVER=thread.
- Added UDP server: gevent.server.DatagramServer
- A "configure" is now run on libev. This fixes a problem of 'kqueue' not being available on Mac OS X.
- Gevent recognizes some environment variables now:
  - GEVENT_BACKEND allows passing argument to loop, e.g. "GEVENT_BACKEND=select" for force select backend
  - GEVENT_RESOLVER allows choosing resolver class.
  - GEVENT_THREADPOOL allows choosing thread pool class.
- Added new examples: portforwarder, psycopg2_pool.py, threadpool.py, udp_server.py
- Fixed non-embedding build. To build against system libev, remove or rename 'libev' directory. To build against system c-ares, remove or rename 'c-ares'. Thanks to Örjan Persson.

misc:
- gevent.joinall() method now accepts optional 'count' keyword.
- gevent.fork() only calls reinit() in the child process now.
- gevent.run() now returns False when exiting because of timeout or event (previous None).
- Hub got a new method: destroy().
- Hub got a new property: threadpool.

ares.pyx:
- Fixed issue #104: made ares_host_result pickable. Thanks to Shaun Cutts.

pywsgi:
- Removed unused deprecated 'wfile' property from WSGIHandler
- Fixed issue #92: raise IOError on truncated POST requests.
- Fixed issue #93: do not sent multiple "100 continue" responses

core:
- Fixed issue #97: the timer watcher now calls ev_now_update() in start() and again() unless 'update' keyword is passed and set to False.
- add set_syserr_cb() function; it's used by gevent internally.
- gevent now installs syserr callback using libev's set_syserr_cb. This callback is called when libev encounters an error it cannot recover from. The default action is to print a message and abort. With the callback installed, a SystemError() is now raised in the main greenlet.
- renamed 'backend_fd' property to 'fileno()' method. (not available if you build gevent against system libev)
- added 'asynccnt' property (not available if you build gevent against system libev)
- made loop.__repr__ output a bit more compact
- the watchers check the arguments for validness now (previously invalid argument would crash libev).
- The 'async' watcher now has send() method;
- fixed time() function
- libev has been upgraded to latest CVS version.
- libev has been patched to use send()/recv() for evpipe on windows when libev_vfd.h is in effect

resolver_ares:
- Slightly improved compatibility with stdlib's socket in some error cases.

socket:
- Fixed close() method not to reference any globals
- Fixed issue #115: _dummy gets unexpected Timeout arg
- Removed _fileobject used for python 2.4 compatibility in socket.py
- Fixed issue #94: fallback to buffer if memoryview fails in _get_memory on python 2.7

monkey:
- Removed patch_httplib()
- Fixed issue #112: threading._sleep is not patched. Thanks to David LaBissoniere.
- Added get_unpatched() function. However, it is slightly broken at the moment.

backdoor:
- make 'locals()' not spew out __builtin__.__dict__ in backdoor
- add optional banner argument to BackdoorServer

servers:
- add server.DatagramServer;
- StreamServer: 'ssl_enabled' is now a read-only property
- servers no longer have 'kill' method; it has been renamed to 'close'.
- listeners can now be configured as strings, e.g. ':80' or 80
- modify baseserver.BaseServer in such a way that makes it a good base class for both StreamServer and DatagramServer
- BaseServer no longer accepts 'backlog' parameter. It is now done by StreamServer.
- BaseServer implements start_accepting() and stop_accepting() methods
- BaseServer now implements "temporarily stop accepting" strategy
- BaseServer now has _do_read method which does everything except for actually calling accept()/recvfrom()
- pre_start() method is renamed to init_socket()
- renamed _stopped_event to _stop_event
- 'started' is now a read-only property (which actually reports state of _stop_event)
- post_stop() method is removed
- close() now sets _stop_event(), thus setting 'started' to False, thus causing serve_forever() to exit
- _tcp_listener() function is moved from baseserver.py to server.py
- added 'fatal_errors' class attribute which is a tuple of all errnos that should kill the server

coros:
- Semaphore: add _start_notify() method
- Semaphore: avoid copying list of links; rawlink() no longer schedules notification



Release 1.0a3
-------------

Added 'ref' property to all watchers. Settings it to False make watcher call ev_unref/ev_ref appropriately so that this watcher does not prevent loop.run()/hub.join()/run() from exiting.
Made resolver_ares.Resolver use 'ref' property for internal watcher.

In all servers, method "kill" was renamed to "close". The old name is available as deprecated alias.

Added a few properties to the loop: backend_fd, fdchangecnt, timercnt.

Upgraded c-ares to 1.7.5+patch.

Fixed getaddrinfo to return results in the order (::1, IPv4, IPv6).

Fixed getaddrinfo() to handle integer of string type. Thanks to kconor.

Fixed gethostbyname() to handle '' (empty string).

Fixed getaddrinfo() to convert UnicodeEncodeError into error('Int or String expected').

Fixed getaddrinfo() to uses the lowest 16 bits of passed port integer similar to built-in _socket.

Fixed getnameinfo() to call getaddrinfo() to process arguments similar to built-in _socket.

Fixed gethostbyaddr() to use getaddrinfo() to process arguments.

version_info is now a 5-tuple.

Added handle_system_error() method to Hub (used internally).

Fixed Hub's run() method to never exit. This prevent inappropriate switches into parent greenlet.

Fixed Hub.join() to return True if Hub was already dead.

Added 'event' argument to Hub.join().

Added `run()` function to gevent top level package.

Fixed Greenlet.start() to exit silently if greenlet was already started rather than raising :exc:`AssertionError`.

Fixed Greenlet.start() not to schedule another switch if greenlet is already dead.

Fixed gevent.signal() to spawn Greenlet instead of raw greenlet. Also it'll switch into the new greenlet immediately instead of scheduling additional callback.

Do monkey patch create_connection() as gevent's version works better with gevent.socket.socket than the standard create_connection.

pywsgi: make sure we don't try to read more requests if socket operation failed with EPIPE

pywsgi: if we failed to send the reply, change 'status' to socket error so that the logs mention the error.


Release 1.0a2
-------------

Fixed a bug in gevent.queue.Channel class. (Thanks to Alexey Borzenkov)


Release 1.0a1
-------------

TODO:
- gevent.http?
- gevent.httplib?
- gevent.wsgi? (Currently gevent/wsgi.py imports classes from gevent/pywsgi.py)


Backward-incompatible changes:

- Dropped support for Python 2.4.
- `Queue(0)` is now equivalent to an unbound queue and raises :exc:`DeprecationError`. Use :class:`gevent.queue.Channel` if you need a channel.
- Deprecated ability to pass a greenlet instance to :meth:`Greenlet.link`, :meth:`Greenlet.link_value` and :meth:`Greenlet.link_exception`.
- All of :mod:`gevent.core` has been rewritten and the interface is not compatible.
- :exc:`SystemExit` and :exc:`SystemError` now kill the whole process instead of printing a traceback.
- Removed deprecated :class:`util.lazy_property` property.
- Removed :mod:`gevent.dns` module.
- Removed deprecated gevent.sslold module
- Removed deprecated gevent.rawgreenlet module
- Removed deprecated name `GreenletSet` which used to be alias for :class:`Group`.

Release highlights:

- The :mod:`gevent.core` module now wraps libev's API and is not compatible with gevent 0.x.
- Added a concept of pluggable event loops. By default gevent.core.loop is used, which is a wrapper around libev.
- Added a concept of pluggable name resolvers. By default a resolver based on c-ares library is used.
- Added support for multiple OS threads, each new thread will get its own Hub instance with its own event loop.
- The release now includes and embeds the dependencies: libev and c-ares.
- The standard :mod:`signal` works now as expected.
- The unhandled errors are now handled uniformely by `Hub.handle_error` function.
- Added :class:`Channel` class to :mod:`gevent.queue` module. It is equivalent to `Queue(0)` in gevent 0.x, which is deprecated now.
- Added method :meth:`peek` to :class:`Queue` class.
- Added :func:`idle` function which blocks until the event loop is idle.
- Added a way to gracefully shutdown the application by waiting for all outstanding greenlets/servers/watchers: :meth:`Hub.join`.
- Added new :mod:`gevent.ares` C extension which wraps `c-ares` and provides asynchronous DNS resolver.
- Added new :mod:`gevent.resolver_ares` module provides synchronous API on top of :mod:`gevent.ares`.

The :mod:`gevent.socket` module:

- DNS functions now use c-ares library rather than libevent-dns. This fixes a number of problems with name resolving:
  - Issue #2: DNS resolver no longer breaks after `fork()`. You still need to call :func:`gevent.fork` (`os.fork` is monkey
    patched with it if `monkey.patch_all()` was called).
  - DNS resolver no longer ignores `/etc/resolv.conf` and `/etc/hosts`.
- The following functions were added to socket module
  - gethostbyname_ex
  - getnameinfo
  - gethostbyaddr
  - getfqdn
- Removed undocumented bind_and_listen and tcp_listener

The :class:`Hub` object:

- Added :meth:`join` method which waits until the event loop exits or optional timeout expires.
- Added :meth:`wait` method which waits until a watcher has got an event.
- Added :meth:`handle_error` method which is called by all of gevent in case of unhandled exception.
- Added :meth:`print_exception` method which is called by `handle_error` to print the exception traceback.

The :class:`Greenlet` objects:

- Added `__nonzero__` implementation that returns `True` after greenlet was started until it's dead.
  Previously greenlet was `False` after `start()` until it was first switched to.

The mod:`gevent.pool` module:

- It is now possible to add raw greenlets to the pool.
- The :meth:`map` and :meth:`imap` methods now start yielding the results as soon as possible.
- The :meth:`imap_unordered` no longer swallows an exception raised while iterating its argument.

Miscellaneous:

- `gevent.sleep(<negative value>)` no longer raises an exception, instead it does `sleep(0)`.
- Added method `clear` to internal `Waiter` class.
- Removed `wait` method from internal `Waiter` class.
- The :class:`WSGIServer` now sets `max_accept` to 1 if `wsgi.multiprocessing` is set to `True`.
- Added :func:`monkey.patch_module` function that monkey patches module using `__implements__` list provided by gevent module.
  All of gevent modules that replace stdlib module now have `__implements__` attribute.


Release 0.13.6 (May 2, 2011)
----------------------------

- Added ``__copy__`` method to :class:`gevent.local.local` class that implements copy semantics compatible with built-in ``threading.local``. Patch by **Galfy Pundee**.
- Fixed :class:`StreamServer` class to catch ``EWOULDBLOCK`` rather than ``EAGAIN``. This fixes lots of spurious tracebacks on Windows where these two constants are not the same. Patch by **Alexey Borzenkov**.
- Fixed issue #65: :func:`fork` now calls ``event_reinit`` only in the child process; otherwise the process could hang when using libevent2. Patch by **Alexander Boudkar**.


Release 0.13.5 (Apr 21, 2011)
-----------------------------

- Fixed build problem on Python 2.5


Release 0.13.4 (Apr 11, 2011)
-----------------------------

- Fixed :exc:`TypeError` that occurred when ``environ["wsgi.input"].read`` function was called with an integer argument.
- Fixed issue #63: :func:`monkey.patch_thread` now patches :mod:`threading` too, even if it's already imported. Patch by **Shaun Lindsay**.
- Fixed issue #64: :func:`joinall` and :func:`killall` functions used to hang if their argument contained duplicate greenlets.
- Fixed issue #69: :class:`pywsgi.WSGIServer` reported "Connection reset by peer" if the client did not close the connection gracefully after the last request. Such errors are now ignored.
- Fixed issue #67: Made :class:`wsgi.WSGIServer` add ``REQUEST_URI`` to environ. Patch by **Andreas Blixt**.
- Fixed issue #71: monkey patching ``httplib`` with :mod:`gevent.httplib` used to break ``HTTPSConnection``. Patch by **Nick Barkas**.
- Fixed issue #74: :func:`create_connection <gevent.socket.create_connection>` now raises proper exception when ``getaddrinfo`` fails.
- Fixed :meth:`BaseServer.__repr__` method, :attr:`BaseServer.server_host` and :attr:`BaseServer.server_port` attributes to handle the case of ``AF_UNIX`` addresses properly. Previously they assumed address is always a tuple.
- Fixed :class:`pywsgi.WSGIServer` to handle ``AF_UNIX`` listeners. The server now sets ``environ["SERVER_NAME"]`` and ``environ["SERVER_PORT"]`` to empty string in such case.
- Make :class:`StreamServer` (and thus :class:`pywsgi.WSGIServer`) accept up to 100 connections per one readiness notification. This behaviour is controlled by :attr:`StreamServer.max_accept` class attribute.
- If bind fails, the servers now include the address that caused bind to fail in the error message.


Release 0.13.3 (Feb 7, 2011)
----------------------------

- Fixed typo in :mod:`gevent.httplib` that rendered it unusable.
- Removed unnecessary delay in :func:`getaddrinfo <gevent.socket.getaddrinfo>` by calling ``resolve_ipv4`` and ``resolve_ipv6`` concurrently rather than sequentially in ``AF_UNSPEC`` case.


Release 0.13.2 (Jan 28, 2011)
-----------------------------

- Added :mod:`gevent.httplib` -- **experimental** support for libevent-http client (issue #9). Thanks to **Tommie Gannert**, **Örjan Persson**.
- Fixed crash on Mac OS X (issue #31). Patch by **Alexey Borzenkov**.
- Fixed compatiblity of :mod:`gevent.wsgi` with libevent2 (issue #62).
- Fixed compilation issues with libevent2. Patch by **Ralf Schmitt**.
- Fixed :mod:`pywsgi` not to use chunked transfer encoding in case of 304 and 204 responses as it creates a non-empty message body which is against RFC and causes some browsers to fail. Patch by **Nicholas Piël**.
- Fixed :func:`socket.getaddrinfo` to handle ``AF_UNSPEC`` properly and resolve service names (issue #56). Thanks to **Elizabeth Jennifer Myers**.
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
- Fixed :class:`wsgi.WSGIServer` to reply with 500 error immediatelly if the application raises an error (issue #58). Thanks to **Jon Aslund**.
- Added :func:`monkey.patch_httplib` function which is disabled by default.
- Added *httplib* parameter to :func:`monkey.patch_all` (defaults to ``False``).
- Added :func:`write <core.buffer.write>` method to :class:`core.buffer`.
- Fixed :exc:`OverflowError` that could happen in :meth:`core.event.__str__`.
- Made :meth:`http_request.get_input_headers` return header names in lower case.
- Fixed :class:`StreamServer` to accept *ciphers* as an SSL argument.
- Added ``build_exc --cython=`` option to ``setup.py``. Patch by **Ralf Schmitt**.
- Updated :class:`local <gevent.local.local>` to raise :exc:`AttributeError` if ``__dict__`` attribute is set or deleted.


Release 0.13.1 (Sep 23, 2010)
-----------------------------

Release highlights:

- Fixed :mod:`monkey` to patch :func:`socket.create_connection <gevent.socket.create_connection>`.
- Updated :mod:`gevent.ssl` module to fully match the functionality of :mod:`ssl` on Python 2.7.
- Fixed :meth:`Group.join` to handle ``raise_error=True`` properly, it used to raise :exc:`TypeError` (issue #36). Thanks to by **David Hain**.
- Fixed :mod:`gevent.wsgi` and :mod:`gevent.pywsgi` to join multiple ``Cookie`` headers (issue #40).
- Fixed :func:`select <gevent.select.select>` to recognize ``long`` arguments in addition to ``int``.
- Fixed :meth:`Semaphore.acquire` to return ``False`` when timeout expires instead of raising :exc:`AssertionError` (issue #39). Patch by **Erik Näslund**.
- Fixed :meth:`JoinableQueue.join` to return immediatelly if queue is already empty (issue #45). Patch by **Dmitry Chechik**.
- Deprecated :mod:`gevent.sslold` module.

:mod:`gevent.socket` module:

- Overrode :meth:`socket.shutdown` method to interrupt read/write operations on socket.
- Fixed possible :exc:`NameError` in :meth:`socket.connect_ex` method. Patch by **Alexey Borzenkov**.
- Fixed socket leak in :func:`create_connection` function.
- Made :mod:`gevent.socket` import all public items from stdlib :mod:`socket` that do not do I/O.

:mod:`gevent.ssl` module:

- Imported a number of patches from stdlib by **Antoine Pitrou**:

  - Calling :meth:`makefile` method on an SSL object would prevent the underlying socket from being closed until all objects get truely destroyed (Python issue #5238).
  - SSL handshake would ignore the socket timeout and block indefinitely if the other end didn't respond (Python issue #5103).
  - When calling :meth:`getpeername` in ``SSLSocket.__init__``, only silence exceptions caused by the "socket not connected" condition.

- Added support for *ciphers* argument.
- Updated ``SSLSocket.send`` and ``SSLSocket.recv`` methods to match the behavior of stdlib :mod:`ssl` better.
- Fixed :class:`ssl.SSLObject` to delete events used by other greenlets when closing the instance (issue #34).

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
-----------------------------

Release highlights:

- Added :mod:`gevent.server` module with :class:`StreamServer` class for easy implementing of TCP and SSL servers.
- Added :mod:`gevent.baseserver` module with :class:`BaseServer` class.
- Added new implementation of :mod:`gevent.pywsgi` based on :mod:`gevent.server`. Contributed by **Ralf Schmitt**.
- Added :mod:`gevent.local` module. Fixed issue #24. Thanks to **Ted Suzman**.
- Fixed a number of bugs in :mod:`gevent.wsgi` module.
- Fixed issue #26: closing a socket now interrupts all pending read/write operations on it.
- Implemented workaround that prevents greenlets from leaking ``exc_info``.
- Fixed :meth:`socket.sendall` to use buffer object to prevent string copies.
- Made the interfaces of :mod:`gevent.wsgi` and :mod:`gevent.pywsgi` much more similar to each other.
- Fixed compilation on Windows with libevent-2.
- Improved Windows compatibility. Fixed issue #30. Thanks to **Luigi Pugnetti**.
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

- Fixed issues #26 and #34: closing the socket while reading/writing/connecting is now safe. Thanks to **Cyril Bay**.
- Imported :func:`getfqdn` from :mod:`socket` module.
- The module now uses ``sys.platform`` to detect Windows rather than :mod:`platform` module.
- Fixed issue #27: :func:`getaddrinfo` used to handle the case when *socktype* or *proto* were equal to ``0``. Thanks to **Randall Leeds**.

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
- Fixed issue #20: :func:`sleep` now raises :exc:`IOError` if passed a negative argument.
- Remove the code related to finding out libevent version from setup.py as macro ``USE_LIBEVENT_?`` is no longer needed to build ``gevent.core``.
- Increased default backlog in all servers (from 5 to 256). Thanks to **Nicholas Piël**.
- Fixed doc/conf.py to work in Python older than 2.6. Thanks to **Örjan Persson**.
- Silented SystemError raised in :mod:`backdoor` when a client typed ``quit()``.
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
----------------------------

* Fixed http server to put the listening socket into a non-blocking mode. Contributed by **Ralf Schmitt**.


Release 0.12.1 (Feb 26, 2010)
-----------------------------

* Removed a symlink from the distribution (that causes pip to fail). Thanks to **Brad Clements** for reporting it.
* setup.py: automatically create symlink from ``build/lib.../gevent/core.so`` to ``gevent/core.so``.
* :mod:`gevent.socket`: Improved compatibility with stdlib's socket:

  - Fixed :class:`socket <gevent.socket.socket>` to raise ``timeout("timed out")`` rather than simply ``timeout``.
  - Imported ``_GLOBAL_DEFAULT_TIMEOUT`` from standard :mod:`socket` module instead of creating a new object.


Release 0.12.0 (Feb 5, 2010)
----------------------------

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
-----------------------------

* Fixed :mod:`wsgi` to unquote ``environ['PATH_INFO']`` before passing to application.
* Added ``SERVER_SOFTWARE`` variable to :mod:`wsgi` environ.
* Fixed bug in :meth:`JoinableQueue.task_done` that caused :class:`ValueError` to be raised incorrectly here.
* Fixed :mod:`gevent.socket` not to fail with :class:`ImportError` if Python was not built with ssl support.


Release 0.11.1 (Nov 15, 2009)
-----------------------------

* Fixed bug in :func:`select.select` function. Passing non-empty list of write descriptors used to cause this function to fail.
* Changed setup.py to go ahead with the compilation even if the actual version of libevent cannot be determined (version 1.x.x is assumed in that case).

Contributed by **Ludvig Ericson**:

* Fixed :mod:`wsgi`'s ``start_response`` to recognize *exc_info* argument.
* Fixed setup.py to look for libevent.dylib rather than .so on Darwin platforms.


Release 0.11.0 (Oct 9, 2009)
----------------------------

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
-----------------------------

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
---------------------------

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
----------------------------

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
  Instead of returning it raises :class:`DispatchExit`.
* Added :func:`reinit` function - wrapper for libevent's ``event_reinit``.
  This function is a must have at least for daemons, as it fixes ``epoll`` and some others eventloops to work after ``fork``.
* Trying to use gevent in another thread will now raise an exception immediately, since it's not implemented.
* Added a few more convenience methods ``spawn_link[exception/value]`` to ``proc.RunningProcSet``.
* Fixed ``setup.py`` not to depend on ``setuptools``.
* Removed ``gevent.timeout``. Use :class:`gevent.Timeout`.


Release 0.9.1 (Jul 9, 2009)
---------------------------

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
---------------------------

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

