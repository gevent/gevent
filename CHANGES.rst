===========
 Changelog
===========

.. currentmodule:: gevent

.. towncrier release notes start

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
  See :issue:`issue1641`.
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
  See :issue:`issue1437`.
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


----
