===========
 Changelog
===========

.. currentmodule:: gevent

.. towncrier release notes start


1.5.0 (2020-04-10)
==================

- Make `gevent.lock.RLock.acquire` accept the *timeout* parameter.
- Fix an ``AttributeError`` when wrapping gevent's ``FileObject``
  around an opened text stream. Reported in :issue:`1542` by
  dmrlawson.
- Fix compilation of libuv on AIX and Solaris 10. See :pr:`1549` and :pr:`1548`
  by Arnon Yaari.

1.5a4 (2020-03-23)
==================

Platform and Packaging Updates
------------------------------

- Python version updates: gevent is now tested with CPython 3.6.10,
  3.7.7 and 3.8.2. It is also tested with PyPy2 7.3 and PyPy 3.6
  7.3.

- The include directories used to compile the C extensions have been
  tweaked with the intent of making it easier to use older debug
  versions of Python. See :issue:`1461`.

- The binary wheels and installed package no longer include generated
  C source files and headers. Also excluded are Cython .pxd files,
  which were never documented. Please file an issue if you miss these.

Library and Dependency Updates
------------------------------

- Upgrade libev from 4.25 to 4.31 and update its embedded
  ``config.guess`` to the latest. See :issue:`1504`.

  .. important::

     libev, when built with ``EV_VERIFY >= 2``, now performs
     verification of file descriptors when IO watchers are started
     *and* when they are stopped. If you first close a file descriptor
     and only then stop an associated watcher, libev will abort the
     process.

     Using the standard gevent socket and file objects handles this
     automatically, but if you're using the IO watchers directly,
     you'll need to watch out for this.

     The binary wheels gevent distributes *do not* set ``EV_VERIFY``
     and don't have this issue.

- Make libuv and libev use the Python memory allocators. This assists
  with debugging. The event libraries allocate small amounts of memory
  at startup. The allocation functions have to take the GIL, but
  because of the limited amount of actual allocation that gets done
  this is not expected to be a bottleneck.

- Update the bundled ``tblib`` library to the unreleased 1.7.0
  version. The only change is to add more attributes to ``Frame`` and ``Code``
  objects for pytest compatibility. See :pr:`1541`.

Potentially Breaking Changes
----------------------------

- Remove the magic proxy object ``gevent.signal``. This served as both
  a deprecated alias of `gevent.signal_handler` *and* the module
  `gevent.signal`. This made it confusing to humans and static
  analysis tools alike. The alias was deprecated since gevent 1.1b4.
  See :issue:`1596`.

Other
-----

- Make `gevent.subprocess.Popen.communicate` raise exceptions raised
  by reading from the process, like the standard library. In
  particular, under Python 3, if the process output is being decoded
  as text, this can now raise ``UnicodeDecodeError``. Reported in
  :issue:`1510` by Ofer Koren.

- Make `gevent.subprocess.Popen.communicate` be more careful about
  closing files. Previously if a timeout error happened, a second call
  to ``communicate`` might not close the pipe.

- Add `gevent.contextvars`, a cooperative version of `contextvars`.
  This is available to all Python versions. On Python 3.7 and above,
  where `contextvars` is a standard library module, it is
  monkey-patched by default. See :issue:`1407`.

- Use `selectors.PollSelector` as the `selectors.DefaultSelector`
  after monkey-patching if `select.poll` was defined. Previously,
  gevent replaced it with `selectors.SelectSelector`, which has a
  different set of limitations (e.g., on certain platforms such as
  glibc Linux, it has a hardcoded limitation of only working with file
  descriptors < 1024). See :issue:`1466` reported by Sam Wong.

- Make the dnspython resolver work if dns python had been imported
  before the gevent resolver was initialized. Reported in
  :issue:`1526` by Chris Utz and Josh Zuech.


1.5a3 (2020-01-01)
==================

- Python version updates: gevent is now tested with CPython 2.7.17,
  3.5.9, 3.6.9, 3.7.5 and 3.8.0 (final). It is also tested with PyPy2
  7.2 and PyPy 3.6 7.2

- Fix using monkey-patched ``threading.Lock`` and ``threading.RLock``
  objects as spin locks by making them call ``sleep(0)`` if they
  failed to acquire the lock in a non-blocking call. This lets other
  callbacks run to release the lock, simulating preemptive threading.
  Using spin locks is not recommended, but may have been done in code
  written for threads, especially on Python 3. See :issue:`1464`.

- Fix Semaphore (and monkey-patched threading locks) to be fair. This
  eliminates the rare potential for starvation of greenlets. As part
  of this change, the low-level method ``rawlink`` of Semaphore,
  Event, and AsyncResult now always remove the link object when
  calling it, so ``unlink`` can sometimes be optimized out. See
  :issue:`1487`.

- Make ``gevent.pywsgi`` support ``Connection: keep-alive`` in
  HTTP/1.0. Based on :pr:`1331` by tanchuhan.

- Fix a potential crash using ``gevent.idle()`` when using libuv. See
  :issue:`1489`.

- Fix some potential crashes using libuv async watchers.

- Make ``ThreadPool`` consistently raise ``InvalidThreadUseError``
  when ``spawn`` is called from a thread different than the thread
  that created the threadpool. This has never been allowed, but was
  inconsistently enforced. On gevent 1.3 and before, this would always
  raise "greenlet error: invalid thread switch," or ``LoopExit``. On
  gevent 1.4, it *could* raise ``LoopExit``, depending on the number
  of tasks, but still, calling it from a different thread was likely
  to corrupt libev or libuv internals.

- Remove some undocumented, deprecated functions from the threadpool module.

- libuv: Fix a perceived slowness spawning many greenlets at the same time
  without yielding to the event loop while having no active IO
  watchers or timers. If the time spent launching greenlets exceeded
  the switch interval and there were no other active watchers, then
  the default IO poll time of about .3s would elapse between spawning
  batches. This could theoretically apply for any non-switching
  callbacks. This can be produced in synthetic benchmarks and other
  special circumstances, but real applications are unlikely to be
  affected. See :issue:`1493`.

- Fix using the threadpool inside a script or module run with ``python
  -m gevent.monkey``. Previously it would use greenlets instead of
  native threads. See :issue:`1484`.

- Fix potential crashes in the FFI backends if a watcher was closed
  and stopped in the middle of a callback from the event loop and then
  raised an exception. This could happen if the hub's ``handle_error``
  function was poorly customized, for example. See :issue:`1482`

- Make ``gevent.killall`` stop greenlets from running that hadn't been
  run yet. This make it consistent with ``Greenlet.kill()``. See
  :issue:`1473` reported by kochelmonster.

- Make ``gevent.spawn_raw`` set the ``loop`` attribute on returned
  greenlets. This lets them work with more gevent APIs, notably
  ``gevent.killall()``. They already had dictionaries, but this may
  make them slightly larger, depending on platform (on CPython 2.7
  through 3.6 there is no apparent difference for one attribute but on
  CPython 3.7 and 3.8 dictionaries are initially empty and only
  allocate space once an attribute is added; they're still smaller
  than on earlier versions though).


File Object Changes
-------------------

.. caution:: There may be breaking changes here for applications that
             relied on the old behaviour. The old behaviour was under
             specified and inconsistent and really only worked
             consistently with 'wb' and 'rb' modes, so most
             applications shouldn't be affected.

- The file objects (``FileObjectPosix``, ``FileObjectThread``) now
  consistently support text and binary modes. If neither 'b' nor 't' is given
  in the mode, they will read and write native strings. If 't' is
  given, they will always work with unicode strings, and 'b' will
  always work with byte strings. (``FileObjectPosix`` already worked this
  way.) See :issue:`1441`.

- The file objects accept *encoding*, *errors* and *newline*
  arguments. On Python 2, these are only used if 't' is in the mode.

- The default mode for ``FileObjectPosix`` changed from ``rb`` to simply
  ``r``, for consistency with the other file objects and the standard
  `open` and :func:`io.open` functions.

- Fix ``FileObjectPosix`` improperly being used from multiple
  greenlets. Previously this was hidden by forcing buffering, which
  raised ``RuntimeError``.


1.5a2 (2019-10-21)
==================

- Add support for CPython 3.8.0. (Windows wheels are not yet available.)

- Update to Cython 0.29.13 and cffi 1.12.3.

- Add an ``--module`` option to ``gevent.monkey`` allowing to run a Python
  module rather than a script. See :pr:`1440`.

- Improve the way joining the main thread works on Python 3.

- Implement ``SSLSocket.verify_client_post_handshake()`` when available.

- Fix tests when TLS1.3 is supported.

- Disable Nagle's algorithm in the backdoor server. This can improve
  interactive response time.

- Test on Python 3.7.4. There are important SSL test fixes.

1.5a1 (2019-05-02)
==================

Platform and Packaging Updates
------------------------------

- Python version updates: gevent is now tested with CPython 2.7.16,
  3.5.6, 3.6.8, and 3.7.2. It is also tested with PyPy2 7.1 and PyPy 3.6
  7.1 (PyPy 7.0 and 7.1 were not capable of running SSL tests on Travis
  CI).

- Support for Python 3.4 has been removed, as that version is no
  longer supported uptstream.

- gevent binary wheels are now manylinux2010 and include libuv
  support. pip 19 is needed to install them. See :issue:`1346`.

- gevent is now compiled with Cython 0.29.6 and cffi 1.12.2.

- gevent sources include a pyproject.toml file, specifying the build
  requirements and enabling build isolation. pip 18 or above is needed
  to take advantage of this. See :issue:`1180`.

- libev-cffi: Let the compiler fill in the definition of ``nlink_t`` for
  ``st_nlink`` in ``struct stat``, instead of trying to guess it
  ourself. Reported in :issue:`1372` by Andreas Schwab.

- Remove the ``Makefile``. Its most useful commands, ``make clean``
  and ``make distclean``, can now be accomplished in a cross-platform
  way using ``python setup.py clean`` and ``python setup.py clean
  -a``, respectively. The remainder of the ``Makefile`` contained
  Travis CI commands that have been moved to ``.travis.yml``.

- Deprecate the ``EMBED`` and ``LIBEV_EMBED``, etc, build-time environment
  variables. Instead, use ``GEVENTSETUP_EMBED`` and
  ``GEVENTSETUP_EMBED_LIBEV``. See :issue:`1402`.

- The CFFI backends now respect the embed build-time setting. This allows
  building the libuv backend without embedding libuv (except on Windows).

- Support test resources. This allows disabling tests that use the
  network. See :ref:`limiting-test-resource-usage` for more.


Library and Dependency Updates
------------------------------

- Upgrade libuv from 1.24.0 to 1.27.0.

- Upgrade libev from 4.23 to 4.25 and update its embedded
  ``config.guess`` to the latest.

- Upgrade c-ares from 1.14 to 1.15.

- dnspython >= 1.16.0 is now required for the dnspython resolver.

Bug fixes
---------

- Python 3.7 subprocess: Copy a ``STARTUPINFO`` passed as a parameter.
  Contributed by AndCycle in :pr:`1352`.

- subprocess: ``WIFSTOPPED`` and ``SIGCHLD`` are now handled for
  determining ``Popen.returncode``. See
  https://bugs.python.org/issue29335

- subprocess: No longer close redirected FDs if they are in
  ``pass_fds``. This is `a bugfix from Python 3.7
  <https://bugs.python.org/issue32270>`_ applied to all versions
  gevent runs on.

- Fix certain operations on a Greenlet in an invalid state (with an
  invalid parent) to raise a `TypeError` sooner rather than an
  `AttributeError` later. This is also slightly faster on CPython with
  Cython. Inspired by :issue:`1363` as reported by Carson Ip. This
  means that some extreme corner cases that might have passed by
  replacing a Greenlet's parent with something that's not a gevent hub
  now no longer will.

- Fix: The ``spawning_stack`` for Greenlets on CPython should now have
  correct line numbers in more cases. See :pr:`1379`.

Enhancements
------------

- The result of ``gevent.ssl.SSLSocket.makefile()`` can be used as a
  context manager on Python 2.

- Python 2: If the backport of the ``_thread_`` module from
  ``futures`` has already been imported at monkey-patch time, also
  patch this module to be consistent. The ``pkg_resources`` package
  imports this, and ``pkg_resources`` is often imported early on
  Python 2 for namespace packages, so if ``futures`` is installed this
  will likely be the case.

- Python 2: Avoid a memory leak when an `io.BufferedWriter` is wrapped
  around a socket. Reported by Damien Tournoud in :issue:`1318`.

- Avoid unbounded memory usage when creating very deep spawn trees.
  Reported in :issue:`1371` by dmrlawson.

- Win: Make ``examples/process.py`` do something useful. See
  :pr:`1378` by Robert Iannucci.

- Spawning greenlets can be up to 10% faster. See :pr:`1379`.
