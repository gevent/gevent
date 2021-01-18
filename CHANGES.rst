===========
 Changelog
===========

.. currentmodule:: gevent

.. towncrier release notes start

21.1.1 (2021-01-18)
===================

Bugfixes
--------

Fix a ``TypeError`` on startup on Python 2 with ``zope.schema``
installed. Reported by Josh Zuech.


21.1.0 (2021-01-15)
===================

Changes
-------

- Supporting newer releases and the ``arm64`` platform required dropping building binary wheels for manylinux 3.6. Users of that version of Python will have to `build from source <https://www.gevent.org/development/installing_from_source.html>`__.

Bugfixes
--------

- Make gevent ``FileObjects`` more closely match the semantics of native
  file objects for the ``name`` attribute:

  - Objects opened from a file descriptor integer have that integer as
    their ``name.`` (Note that this is the Python 3 semantics; Python 2
    native file objects returned from ``os.fdopen()`` have the string
    "<fdopen>" as their name , but here gevent always follows Python 3.)
  - The ``name`` remains accessible after the file object is closed.

  Thanks to Dan Milon.
  See :issue:`1745`.


Misc
----

Make ``gevent.event.AsyncResult`` print a warning when it detects improper
cross-thread usage instead of hanging.

``AsyncResult`` has *never* been safe to use from multiple threads.
It, like most gevent objects, is intended to work with greenlets from
a single thread. Using ``AsyncResult`` from multiple threads has
undefined semantics. The safest way to communicate between threads is
using an event loop async watcher.

Those undefined semantics changed in recent gevent versions, making it
more likely that an abused ``AsyncResult`` would misbehave in ways
that could cause the program to hang.

Now, when ``AsyncResult`` detects a situation that would hang, it
prints a warning to stderr. Note that this is best-effort, and hangs
are still possible, especially under PyPy 7.3.3.

At the same time, ``AsyncResult`` is tuned to behave more like it did
in older versions, meaning that the hang is once again much less
likely. If you were getting lucky and using ``AsyncResult``
successfully across threads, this may restore your luck. In addition,
cross-thread wakeups are faster. Note that the gevent hub now uses an
extra file descriptor to implement this.

Similar changes apply to ``gevent.event.Event`` (see :issue:`1735`).

See :issue:`1739`.


----


20.12.1 (2020-12-27)
====================


Features
--------

- Make :class:`gevent.Greenlet` objects function as context managers.
  When the ``with`` suite finishes, execution doesn't continue until the
  greenlet is finished. This can be a simpler alternative to a
  :class:`gevent.pool.Group` when the lifetime of greenlets can be
  lexically scoped.

  Suggested by André Caron.
  See :issue:`1324`.


Bugfixes
--------

- Make gevent's ``Semaphore`` objects properly handle native thread
  identifiers larger than can be stored in a C ``long`` on Python 3,
  instead of raising an ``OverflowError``.

  Reported by TheYOSH.
  See :issue:`1733`.


----


20.12.0 (2020-12-22)
====================


Features
--------

- Make worker threads created by :class:`gevent.threadpool.ThreadPool` install
  the :func:`threading.setprofile` and :func:`threading.settrace` hooks
  while tasks are running. This provides visibility to profiling and
  tracing tools like yappi.

  Reported by Suhail Muhammed.
  See :issue:`1678`.


Bugfixes
--------

- Incorrectly passing an exception *instance* instead of an exception
  *type* to `gevent.Greenlet.kill` or `gevent.killall` no longer prints
  an exception to stderr.
  See :issue:`1663`.
- Make destroying a hub try harder to more forcibly stop loop processing
  when there are outstanding callbacks or IO operations scheduled.

  Thanks to Josh Snyder (:issue:`1686`) and Jan-Philip Gehrcke
  (:issue:`1669`).
  See :issue:`1686`.
- Improve the ability to use monkey-patched locks, and
  `gevent.lock.BoundedSemaphore`, across threads, especially when the
  various threads might not have a gevent hub or any other active
  greenlets. In particular, this handles some cases that previously
  raised ``LoopExit`` or would hang. Note that this may not be reliable
  on PyPy on Windows; such an environment is not currently recommended.

  The semaphore tries to avoid creating a hub if it seems unnecessary,
  automatically creating one in the single-threaded case when it would
  block, but not in the multi-threaded case. While the differences
  should be correctly detected, it's possible there are corner cases
  where they might not be.

  If your application appears to hang acquiring semaphores, but adding a
  call to ``gevent.get_hub()`` in the thread attempting to acquire the
  semaphore before doing so fixes it, please file an issue.
  See :issue:`1698`.
- Make error reporting when a greenlet suffers a `RecursionError` more
  reliable.

  Reported by Dan Milon.
  See :issue:`1704`.
- gevent.pywsgi: Avoid printing an extra traceback ("TypeError: not
  enough arguments for format string") to standard error on certain
  invalid client requests.

  Reported by Steven Grimm.
  See :issue:`1708`.
- Add support for PyPy2 7.3.3.
  See :issue:`1709`.
- Python 2: Make ``gevent.subprocess.Popen.stdin`` objects have a
  ``write`` method that guarantees to write the entire argument in
  binary, unbuffered mode. This may require multiple trips around the
  event loop, but more closely matches the behaviour of the Python 2
  standard library (and gevent prior to 1.5). The number of bytes
  written is still returned (instead of ``None``).
  See :issue:`1711`.
- Make `gevent.pywsgi` stop trying to enforce the rules for reading chunked input or
  ``Content-Length`` terminated input when the connection is being
  upgraded, for example to a websocket connection. Likewise, if the
  protocol was switched by returning a ``101`` status, stop trying to
  automatically chunk the responses.

  Reported by Kavindu Santhusa.
  See :issue:`1712`.
- Remove the ``__dict__`` attribute from `gevent.socket.socket` objects. The
  standard library socket do not have a ``__dict__``.

  Noticed by Carson Ip.

  As part of this refactoring, share more common socket code between Python 2
  and Python 3.
  See :issue:`1724`.

----


20.9.0 (2020-09-22)
===================


Features
--------

- The embedded libev is now asked to detect the availability of
  ``clock_gettime`` and use the realtime and/or monotonic clocks, if
  they are available.

  On Linux, this can reduce the number of system calls libev makes.
  Originally provided by Josh Snyder.
  See :issue:`1648`.


Bugfixes
--------

- On CPython, depend on greenlet >= 0.4.17. This version is binary
  incompatible with earlier releases on CPython 3.7 and later.

  On Python 3.7 and above, the module ``gevent.contextvars`` is no
  longer monkey-patched into the standard library. contextvars are now
  both greenlet and asyncio task local. See :issue:`1656`.
  See :issue:`1674`.
- The ``DummyThread`` objects created automatically by certain
  operations when the standard library threading module is
  monkey-patched now match the naming convention the standard library
  uses ("Dummy-12345"). Previously (since gevent 1.2a2) they used
  "DummyThread-12345".
  See :issue:`1659`.
- Fix compatibility with dnspython 2.

  .. caution:: This currently means that it can be imported. But it
               cannot yet be used. gevent has a pinned dependency on
               dnspython < 2 for now.

  See :issue:`1661`.


----


20.6.2 (2020-06-16)
===================


Features
--------

- It is now possible to build and use the embedded libuv on a Cygwin
  platform.

  Note that Cygwin is not an officially supported platform of upstream
  libuv and is not tested by gevent, so the actual working status is
  unknown, and this may bitrot in future releases.

  Thanks to berkakinci for the patch.
  See :issue:`1645`.


Bugfixes
--------

- Relax the version constraint for psutil on PyPy.

  Previously it was pinned to 5.6.3 for PyPy2, except for on Windows,
  where it was excluded. It is now treated the same as CPython again.
  See :issue:`1643`.


----


20.6.1 (2020-06-10)
===================


Features
--------

- gevent's CI is now tested on Ubuntu 18.04 (Bionic), an upgrade from
  16.04 (Xenial).
  See :issue:`1623`.


Bugfixes
--------

- On Python 2, the dnspython resolver can be used without having
  selectors2 installed. Previously, an ImportError would be raised.
  See :issue:`1641`.
- Python 3 ``gevent.ssl.SSLSocket`` objects no longer attempt to catch
  ``ConnectionResetError`` and treat it the same as an ``SSLError`` with
  ``SSL_ERROR_EOF`` (typically by suppressing it).

  This was a difference from the way the standard library behaved (which
  is to raise the exception). It was added to gevent during early
  testing of OpenSSL 1.1 and TLS 1.3.
  See :issue:`1637`.


----


20.6.0 (2020-06-06)
===================


Features
--------

- Add ``gevent.selectors`` containing ``GeventSelector``. This selector
  implementation uses gevent details to attempt to reduce overhead when
  polling many file descriptors, only some of which become ready at any
  given time.

  This is monkey-patched as ``selectors.DefaultSelector`` by default.

  This is available on Python 2 if the ``selectors2`` backport is
  installed. (This backport is installed automatically using the
  ``recommended`` extra.) When monkey-patching, ``selectors`` is made
  available as an alias to this module.
  See :issue:`1532`.
- Depend on greenlet >= 0.4.16. This is required for CPython 3.9 and 3.10a0.
  See :issue:`1627`.
- Add support for Python 3.9.

  No binary wheels are available yet, however.
  See :issue:`1628`.


Bugfixes
--------

- ``gevent.socket.create_connection`` and
  ``gevent.socket.socket.connect`` no longer ignore IPv6 scope IDs.

  Any IP address (IPv4 or IPv6) is no longer subject to an extra call to
  ``getaddrinfo``. Depending on the resolver in use, this is likely to
  change the number and order of greenlet switches. (On Windows, in
  particular test cases when there are no other greenlets running, it has
  been observed to lead to ``LoopExit`` in scenarios that didn't produce
  that before.)
  See :issue:`1634`.


----


20.5.2 (2020-05-28)
===================


Bugfixes
--------

- Forking a process that had use the threadpool to run tasks that
  created their own hub would fail to clean up the threadpool by raising
  ``greenlet.error``.
  See :issue:`1631`.


----


20.5.1 (2020-05-26)
===================


Features
--------

- Waiters on Event and Semaphore objects that call ``wait()`` or
  ``acquire()``, respectively, that find the Event already set, or the
  Semaphore available, no longer "cut in line" and run before any
  previously scheduled greenlets. They now run in the order in which
  they arrived, just as waiters that had to block in those methods do.
  See :issue:`1520`.
- Update tested PyPy version from 7.3.0 to 7.3.1 on Linux.
  See :issue:`1569`.
- Make ``zope.interface``, ``zope.event`` and (by extension)
  ``setuptools`` required dependencies. The ``events`` install extra now
  does nothing and will be removed in 2021.
  See :issue:`1619`.
- Update bundled libuv from 1.36.0 to 1.38.0.
  See :issue:`1621`.
- Update bundled c-ares from 1.16.0 to 1.16.1.

  On macOS, stop trying to adjust c-ares headers to make them
  universal.
  See :issue:`1624`.


Bugfixes
--------

- Make gevent locks that are monkey-patched usually work across native
  threads as well as across greenlets within a single thread. Locks that
  are only used in a single thread do not take a performance hit. While
  cross-thread locking is relatively expensive, and not a recommended
  programming pattern, it can happen unwittingly, for example when
  using the threadpool and ``logging``.

  Before, cross-thread lock uses might succeed, or, if the lock was
  contended, raise ``greenlet.error``. Now, in the contended case, if
  the lock has been acquired by the main thread at least once, it should
  correctly block in any thread, cooperating with the event loop of both
  threads. In certain (hopefully rare) cases, it might be possible for
  contended case to raise ``LoopExit`` when previously it would have
  raised ``greenlet.error``; if these cases are a practical concern,
  please open an issue.

  Also, the underlying Semaphore always behaves in an atomic fashion (as
  if the GIL was not released) when PURE_PYTHON is set. Previously, it
  only correctly did so on PyPy.
  See :issue:`1437`.
- Rename gevent's C accelerator extension modules using a prefix to
  avoid clashing with other C extensions.
  See :issue:`1480`.
- Using ``gevent.wait`` on an ``Event`` more than once, when that Event
  is already set, could previously raise an AssertionError.

  As part of this, exceptions raised in the main greenlet will now
  include a more complete traceback from the failing greenlet.
  See :issue:`1540`.
- Avoid closing the same Python libuv watcher IO object twice. Under
  some circumstances (only seen on Windows), that could lead to program
  crashes.
  See :issue:`1587`.
- gevent can now be built using Cython 3.0a5 and newer. The PyPI
  distribution uses this version.

  The libev extension was incompatible with this. As part of this,
  certain internal, undocumented names have been changed.

  (Technically, gevent can be built with Cython 3.0a2 and above.
  However, up through 3.0a4 compiling with Cython 3 results in
  gevent's test for memory leaks failing. See `this Cython issue
  <https://github.com/cython/cython/issues/3578>`_.)
  See :issue:`1599`.
- Destroying a hub after joining it didn't necessarily clean up all
  resources associated with the hub, especially if the hub had been
  created in a secondary thread that was exiting. The hub and its parent
  greenlet could be kept alive.

  Now, destroying a hub drops the reference to the hub and ensures it
  cannot be switched to again. (Though using a new blocking API call may
  still create a new hub.)

  Joining a hub also cleans up some (small) memory resources that might
  have stuck around for longer before as well.
  See :issue:`1601`.
- Fix some potential crashes under libuv when using
  ``gevent.signal_handler``. The crashes were seen running the test
  suite and were non-deterministic.
  See :issue:`1606`.


----


20.5.0 (2020-05-01)
===================


Features
--------

- Update bundled c-ares to version 1.16.0. `Changes <https://c-ares.haxx.se/changelog.html>`_.
  See :issue:`1588`.
- Update all the bundled ``config.guess`` and ``config.sub`` scripts.
  See :issue:`1589`.
- Update bundled libuv from 1.34.0 to 1.36.0.
  See :issue:`1597`.


Bugfixes
--------

- Use ``ares_getaddrinfo`` instead of a manual lookup.

  This requires c-ares 1.16.0.

  Note that this may change the results, in particular their order.

  As part of this, certain parts of the c-ares extension were adapted to
  use modern Cython idioms.

  A few minor errors and discrepancies were fixed as well, such as
  ``gethostbyaddr('localhost')`` working on Python 3 and failing on
  Python 2. The DNSpython resolver now raises the expected TypeError in
  more cases instead of an AttributeError.
  See :issue:`1012`.
- The c-ares and DNSPython resolvers now raise exceptions much more
  consistently with the standard resolver. Types and errnos are
  substantially more likely to match what the standard library produces.

  Depending on the system and configuration, results may not match
  exactly, at least with DNSPython. There are still some rare cases
  where the system resolver can raise ``herror`` but DNSPython will
  raise ``gaierror`` or vice versa. There doesn't seem to be a
  deterministic way to account for this. On PyPy, ``getnameinfo`` can
  produce results when CPython raises ``socket.error``, and gevent's
  DNSPython resolver also raises ``socket.error``.

  In addition, several other small discrepancies were addressed,
  including handling of localhost and broadcast host names.

  .. note:: This has been tested on Linux (CentOS and Ubuntu), macOS,
            and Windows. It hasn't been tested on other platforms, so
            results are unknown for them. The c-ares support, in
            particular, is using some additional socket functions and
            defines. Please let the maintainers know if this introduces
            issues.

  See :issue:`1459`.


----


20.04.0 (2020-04-22)
====================


Features
--------

- Let CI (Travis and Appveyor) build and upload release wheels for
  Windows, macOS and manylinux. As part of this, (a subset of) gevent's
  tests can run if the standard library's ``test.support`` module has
  been stripped.
  See :issue:`1555`.
- Update tested PyPy version from 7.2.0 on Windows to 7.3.1.
  See :issue:`1569`.


Bugfixes
--------

- Fix a spurious warning about watchers and resource leaks on libuv on
  Windows. Reported by Stéphane Rainville.
  See :issue:`1564`.
- Make monkey-patching properly remove ``select.epoll`` and
  ``select.kqueue``. Reported by Kirill Smelkov.
  See :issue:`1570`.
- Make it possible to monkey-patch :mod:`contextvars` before Python 3.7
  if a non-standard backport that uses the same name as the standard
  library does is installed. Previously this would raise an error.
  Reported by Simon Davy.
  See :issue:`1572`.
- Fix destroying the libuv default loop and then using the default loop
  again.
  See :issue:`1580`.
- libuv loops that have watched children can now exit. Previously, the
  SIGCHLD watcher kept the loop alive even if there were no longer any
  watched children.
  See :issue:`1581`.


Deprecations and Removals
-------------------------

- PyPy no longer uses the Python allocation functions for libuv and
  libev allocations.
  See :issue:`1569`.


Misc
----

- See :issue:`1367`.
