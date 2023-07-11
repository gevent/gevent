==================
 Changes for 1.1
==================

.. currentmodule:: gevent

1.1.2 (Jul 21, 2016)
====================

- Python 2: ``sendall`` on a non-blocking socket could spuriously fail
  with a timeout.
- If ``sys.stderr`` has been monkey-patched (not recommended),
  exceptions that the hub reports aren't lost and can still be caught.
  Reported in :issue:`825` by Jelle Smet.
- :class:`selectors.SelectSelector` is properly monkey-patched
  regardless of the order of imports. Reported in :issue:`835` by
  Przemysław Węgrzyn.
- Python 2: ``reload(site)`` no longer fails with a ``TypeError`` if
  gevent has been imported. Reported in :issue:`805` by Jake Hilton.

1.1.1 (Apr 4, 2016)
===================

- Nested callbacks that set and clear an Event no longer cause
  ``wait`` to return prematurely. Reported in :issue:`771` by Sergey
  Vasilyev.
- Fix build on Solaris 10. Reported in :issue:`777` by wiggin15.
- The ``ref`` parameter to :func:`gevent.os.fork_and_watch` was being ignored.
- Python 3: :class:`gevent.queue.Channel` is now correctly iterable, instead of
  raising a :exc:`TypeError`.
- Python 3: Add support for :meth:`socket.socket.sendmsg`,
  :meth:`socket.socket.recvmsg` and :meth:`socket.socket.recvmsg_into`
  on platforms where they are defined. Initial :pr:`773` by Jakub
  Klama.

1.1.0 (Mar 5, 2016)
===================

- Python 3: A monkey-patched :class:`threading.RLock` now properly
  blocks (or deadlocks) in ``acquire`` if the default value for
  *timeout* of -1 is used (which differs from gevent's default of
  None). The ``acquire`` method also raises the same :exc:`ValueError`
  exceptions that the standard library does for invalid parameters.
  Reported in :issue:`750` by Joy Zheng.
- Fix a race condition in :class:`~gevent.event.Event` that made it
  return ``False`` when the event was set and cleared by the same
  greenlet before allowing a switch to already waiting greenlets. (Found
  by the 3.4 and 3.5 standard library test suites; the same as Python
  `bug 13502`_. Note that the Python 2 standard library still has this
  race condition.)
- :class:`~gevent.event.Event` and :class:`~.AsyncResult` now wake
  waiting greenlets in the same (unspecified) order. Previously,
  ``AsyncResult`` tended to use a FIFO order, but this was never
  guaranteed. Both classes also use less per-instance memory.
- Using a :class:`~logging.Logger` as a :mod:`pywsgi` error or request
  log stream no longer produces extra newlines. Reported in
  :issue:`756` by ael-code.
- Windows: Installing from an sdist (.tar.gz) on PyPI no longer
  requires having Cython installed first. (Note that the binary installation
  formats (wheels, exes, msis) are preferred on Windows.) Reported in
  :issue:`757` by Ned Batchelder.
- Issue a warning when :func:`~gevent.monkey.patch_all` is called with
  ``os`` set to False (*not* the default) but ``signal`` is still True
  (the default). This combination of parameters will cause signal
  handlers for ``SIGCHLD`` to not get called. In the future this might
  raise an error. Reported by Josh Zuech.
- Issue a warning when :func:`~gevent.monkey.patch_all` is called more
  than once with different arguments. That causes the cumulative set of all True
  arguments to be patched, which may cause unexpected results.
- Fix returning the original values of certain ``threading``
  attributes from :func:`gevent.monkey.get_original`.

.. _bug 13502: http://bugs.python.org/issue13502

1.1rc5 (Feb 24, 2016)
=====================

- SSL: Attempting to send empty data using the
  :meth:`~socket.socket.sendall` method of a gevent SSL socket that has
  a timeout now returns immediately (like the standard library does),
  instead of incorrectly raising :exc:`ssl.SSLEOFError`. (Note that
  sending empty data with the :meth:`~socket.socket.send`
  method *does* raise ``SSLEOFError`` in
  both gevent and the standard library.) Reported in :issue:`719` by
  Mustafa Atik and Tymur Maryokhin, with a reproducible test case
  provided by Timo Savola.

1.1rc4 (Feb 16, 2016)
=====================

- Python 2: Using the blocking API at import time when multiple
  greenlets are also importing should not lead to ``LoopExit``.
  Reported in :issue:`728` by Garrett Heel.
- Python 2: Don't raise :exc:`OverflowError` when using the ``readline``
  method of the WSGI input stream without a size hint or with a large
  size hint when the client is uploading a large amount of data. (This
  only impacted CPython 2; PyPy and Python 3 already handled this.)
  Reported in :issue:`289` by ggjjlldd, with contributions by Nathan
  Hoad.
- :class:`~gevent.baseserver.BaseServer` and its subclasses like
  :class:`~gevent.pywsgi.WSGIServer` avoid allocating a new closure for
  each request, reducing overhead.
- Python 2: Under 2.7.9 and above (or when the PEP 466 SSL interfaces
  are available), perform the same hostname validation that the
  standard library does; previously this was skipped. Also,
  reading, writing, or handshaking a closed
  :class:`~ssl.SSLSocket` now raises the same :exc:`ValueError`
  the standard library does, instead of an :exc:`AttributeError`.
  Found by updating gevent's copy of the standard library test cases.
  Initially reported in :issue:`735` by Dmitrij D. Czarkoff.
- Python 3: Fix :meth:`~ssl.SSLSocket.unwrap` and SNI callbacks.
  Also raise the correct exceptions for unconnected SSL sockets and
  properly validate SSL hostnames. Found via updated standard library
  tests.
- Python 3: Add missing support for :meth:`socket.socket.sendfile`. Found via updated
  standard library tests.
- Python 3.4+: Add missing support for
  :meth:`socket.socket.get_inheritable` and
  :meth:`~socket.socket.set_inheritable`. Found via updated standard
  library tests.

1.1rc3 (Jan 04, 2016)
=====================

- Python 2: Support the new PEP 466 :mod:`ssl` interfaces on any Python 2
  version that supplies them, not just on the versions it officially
  shipped with. Some Linux distributions, including RedHat/CentOS and
  Amazon have backported the changes to older versions. Reported in
  :issue:`702`.
- PyPy: An interaction between Cython compiled code and the garbage
  collector caused PyPy to crash when a previously-allocated Semaphore
  was used in a ``__del__`` method, something done in the popular
  libraries ``requests`` and ``urllib3``. Due to this and other Cython
  related issues, the Semaphore class is no longer compiled by Cython
  on PyPy. This means that it is now traceable and not exactly as
  atomic as the Cython version, though the overall semantics should
  remain the same. Reported in :issue:`704` by Shaun Crampton.
- PyPy: Optimize the CFFI backend to use less memory (two pointers per
  watcher).
- Python 3: The WSGI ``PATH_INFO`` entry is decoded from URL escapes
  using latin-1, not UTF-8. This improves compliance with PEP 3333 and
  compatibility with some frameworks like Django. Fixed in :pr:`712`
  by Ruben De Visscher.

1.1rc2 (Dec 11, 2015)
=====================

- Exceptions raised by gevent's SSL sockets are more consistent with
  the standard library (e.g., gevent's Python 3 SSL sockets raise
  :exc:`socket.timeout` instead of :exc:`ssl.SSLError`, a change
  introduced in Python 3.2).
- Python 2: gevent's socket's ``sendall`` method could completely ignore timeouts
  in some cases. The timeout now refers to the total time taken by
  ``sendall``.
- gevent's SSL socket's ``sendall`` method should no longer raise ``SSL3_WRITE_PENDING``
  in rare cases when sending large buffers. Reported in :issue:`317`.
- :func:`gevent.signal.signal` now allows resetting (SIG_DFL) and ignoring (SIG_IGN) the
  SIGCHLD signal at the process level (although this may allow race
  conditions with libev child watchers). Reported in :issue:`696` by
  Adam Ning.
- :func:`gevent.spawn_raw` now accepts keyword arguments, as
  previously (incorrectly) documented. Reported in :issue:`680` by Ron
  Rothman.
- PyPy: PyPy 2.6.1 or later is now required (4.0.1 or later is
  recommended).
- The CFFI backend is now built and usable on CPython implementations
  (except on Windows) if ``cffi`` is installed before gevent is
  installed. To use the CFFI backend, set the environment variable
  ``GEVENT_CORE_CFFI_ONLY`` before starting Python. This can aid
  debugging in some cases and helps ensure parity across all
  combinations of supported platforms.
- The CFFI backend now calls the callback of a watcher whose ``args`` attribute is
  set to ``None``, just like the Cython backend does. It also only
  allows ``args`` to be a tuple or ``None``, again matching the Cython backend.
- PyPy/CFFI: Fix a potential crash when using stat watchers.
- PyPy/CFFI: Encode unicode paths for stat watchers using
  :meth:`sys.getfilesystemencoding` like the Cython backend.
- The internal implementation modules ``gevent._fileobject2``,
  ``gevent._fileobject3``, and ``gevent._util`` were removed. These
  haven't been used or tested since 1.1b1.


1.1rc1 (Nov 14, 2015)
=====================

- Windows/Python 3: Finish porting the :mod:`gevent.subprocess` module, fixing a
  large number of failing tests. Examples of failures are in
  :issue:`668` and :issue:`669` reported by srossross.
- Python 3: The SSLSocket class should return an empty ``bytes``
  object on an EOF instead of a ``str``. Fixed in :pr:`674` by Dahoon
  Kim.
- Python 2: Workaround a buffering bug in the stdlib ``io`` module
  that caused ``FileObjectPosix`` to be slower than necessary in some
  cases. Reported in :issue:`675` by WGH-.
- PyPy: Fix a crash. Reported in :issue:`676` by Jay Oster.

  .. caution:: There are some remaining, relatively rare, PyPy
               crashes, but their ultimate cause is unknown (gevent,
               CFFI, greenlet, the PyPy GC?). PyPy users can
               contribute to :issue:`677` to help track them down.
- PyPy: Exceptions raised while handling an error raised by a loop
  callback function behave like the CPython implementation: the
  exception is printed, and the rest of the callbacks continue
  processing.
- If a Hub object with active watchers was destroyed and then another
  one created for the same thread, which itself was then destroyed with
  ``destroy_loop=True``, the process could crash. Documented in
  :issue:`237` and fix based on :pr:`238`, both by Jan-Philip Gehrcke.
- Python 3: Initializing gevent's hub for the first time
  simultaneously in multiple native background threads could fail with
  ``AttributeError`` and ``ImportError``. Reported in :issue:`687` by
  Gregory Petukhov.

1.1b6 (Oct 17, 2015)
====================

- PyPy: Fix a memory leak for code that allocated and disposed of many
  :class:`gevent.lock.Semaphore` subclasses. If monkey-patched, this could
  also apply to :class:`threading.Semaphore` objects. Reported in
  :issue:`660` by Jay Oster.
- PyPy: Cython version 0.23.4 or later must be used to avoid a memory
  leak (`details`_). Thanks to Jay Oster.
- Allow subclasses of :class:`~.WSGIHandler` to handle invalid HTTP client
  requests. Reported by not-bob.
- :class:`~.WSGIServer` more robustly supports :class:`~logging.Logger`-like parameters for
  ``log`` and ``error_log`` (as introduced in 1.1b1, this could cause
  integration issues with gunicorn). Reported in :issue:`663` by Jay
  Oster.
- :class:`~gevent.threading._DummyThread` objects, created in a
  monkey-patched system when :func:`threading.current_thread` is
  called in a new greenlet (which often happens implicitly, such as
  when logging) are much lighter weight. For example, they no longer
  allocate and then delete a :class:`~gevent.lock.Semaphore`, which is
  especially important for PyPy.
- Request logging by :mod:`gevent.pywsgi` formats the status code
  correctly on Python 3. Reported in :issue:`664` by Kevin Chen.
- Restore the ability to take a weak reference to instances of exactly
  :class:`gevent.lock.Semaphore`, which was unintentionally removed
  as part of making ``Semaphore`` atomic on PyPy on 1.1b1. Reported in
  :issue:`666` by Ivan-Zhu.
- Build Windows wheels for Python 3.5. Reported in :pr:`665` by Hexchain Tong.

.. _details: https://mail.python.org/pipermail/cython-devel/2015-October/004571.html

1.1b5 (Sep 18, 2015)
====================

- :mod:`gevent.subprocess` works under Python 3.5. In general, Python 3.5
  has preliminary support. Reported in :issue:`653` by Squeaky.
- :func:`Popen.communicate <gevent.subprocess.Popen.communicate>` honors a ``timeout``
  argument even if there is no way to communicate with the child
  process (none of stdin, stdout and stderr were set to ``PIPE``).
  Noticed as part of the Python 3.5 test suite for the new function
  ``subprocess.run`` but impacts all versions (``timeout`` is an
  official argument under Python 3 and a gevent extension with
  slightly different semantics under Python 2).
- Fix a possible ``ValueError`` from :meth:`Queue.peek <gevent.queue.Queue.peek>`.
  Reported in :issue:`647` by Kevin Chen.
- Restore backwards compatibility for using ``gevent.signal`` as a
  callable, which, depending on the order of imports, could be broken
  after the addition of the ``gevent.signal`` module. Reported in
  :issue:`648` by Sylvain Zimmer.
- gevent blocking operations performed at the top-level of a module
  after the system was monkey-patched under Python 2 could result in
  raising a :exc:`~gevent.hub.LoopExit` instead of completing the expected blocking
  operation. Note that performing gevent blocking operations in the
  top-level of a module is typically not recommended, but this
  situation can arise when monkey-patching existing scripts. Reported
  in :issue:`651` and :issue:`652` by Mike Kaplinskiy.
- ``SIGCHLD`` and ``waitpid`` now work for the pids returned by the
  (monkey-patched) ``os.forkpty`` and ``pty.fork`` functions in the
  same way they do for the ``os.fork`` function. Reported in
  :issue:`650` by Erich Heine.
- :class:`~gevent.pywsgi.WSGIServer` and
  :class:`~gevent.pywsgi.WSGIHandler` do a better job detecting and
  reporting potential encoding errors for headers and the status line
  during :meth:`~gevent.pywsgi.WSGIHandler.start_response` as recommended by the `WSGI
  specification`_. In addition, under Python 2, unnecessary encodings
  and decodings (often a trip through the ASCII encoding) are avoided
  for conforming applications. This is an enhancement of an already
  documented and partially enforced constraint: beginning in 1.1a1,
  under Python 2, ``u'abc'`` would typically previously have been
  allowed, but ``u'\u1f4a3'`` would not; now, neither will be allowed,
  more closely matching the specification, improving debugability and
  performance and allowing for better error handling both by the
  application and by gevent (previously, certain encoding errors could
  result in gevent writing invalid/malformed HTTP responses). Reported
  by Greg Higgins and Carlos Sanchez.
- Code coverage by tests is now reported on `coveralls.io`_.

.. _WSGI specification: https://www.python.org/dev/peps/pep-3333/#the-start-response-callable
.. _coveralls.io: https://coveralls.io/github/gevent/gevent

1.1b4 (Sep 4, 2015)
===================

- Detect and raise an error for several important types of
  programming errors even if Python interpreter optimizations are
  enabled with ``-O`` or ``PYTHONOPTIMIZE``. Previously these would go
  undetected if optimizations were enabled, potentially leading to
  erratic, difficult to debug behaviour.
- Fix an ``AttributeError`` from ``gevent.queue.Queue`` when ``peek``
  was called on an empty ``Queue``. Reported in :issue:`643` by michaelvol.
- Make ``SIGCHLD`` handlers specified to :func:`gevent.signal.signal` work with
  the child watchers that are used by default. Also make
  :func:`gevent.os.waitpid` work with a first argument of -1. (Also
  applies to the corresponding monkey-patched stdlib functions.)
  Noted by users of gunicorn.
- Under Python 2, any timeout set on a socket would be ignored when
  using the results of ``socket.makefile``. Reported in :issue:`644`
  by Karan Lyons.

1.1b3 (Aug 16, 2015)
====================

- Fix an ``AttributeError`` from ``gevent.monkey.patch_builtins`` on
  Python 2 when the `future`_ library is also installed. Reported by
  Carlos Sanchez.
- PyPy: Fix a ``DistutilsModuleError`` or ``ImportError`` if the CFFI
  module backing ``gevent.core`` needs to be compiled when the hub is
  initialized (due to a missing or invalid ``__pycache__`` directory).
  Now, the module will be automtically compiled when gevent is
  imported (this may produce compiler output on stdout). Reported in
  :issue:`619` by Thinh Nguyen and :issue:`631` by Andy Freeland, with
  contributions by Jay Oster and Matt Dupre.
- PyPy: Improve the performance of ``gevent.socket.socket:sendall``
  with large inputs. `bench_sendall.py`_ now performs about as well on
  PyPy as it does on CPython, an improvement of 10x (from ~60MB/s to
  ~630MB/s). See this `pypy bug`_ for details.
- Fix a possible ``TypeError`` when calling ``gevent.socket.wait``.
  Reported in #635 by lanstin.
- ``gevent.socket.socket:sendto`` properly respects the socket's
  blocking status (meaning it can raise EWOULDBLOCK now in cases it
  wouldn't have before). Reported in :pr:`634` by Mike Kaplinskiy.
- Common lookup errors using the :mod:`threaded resolver
  <gevent.resolver_thread>` are no longer always printed to stderr
  since they are usually out of the programmer's control and caught
  explicitly. (Programming errors like ``TypeError`` are still
  printed.) Reported in :issue:`617` by Jay Oster and Carlos Sanchez.
- PyPy: Fix a ``TypeError`` from ``gevent.idle()``. Reported in
  :issue:`639` by chilun2008.
- The :func:`~gevent.pool.Pool.imap_unordered` methods of a pool-like
  object support a ``maxsize`` parameter to limit the number of
  results buffered waiting for the consumer. Reported in :issue:`638`
  by Sylvain Zimmer.
- The class :class:`gevent.queue.Queue` now consistently orders multiple
  blocked waiting ``put`` and ``get`` callers in the order they
  arrived. Previously, due to an implementation quirk this was often
  roughly the case under CPython, but not under PyPy. Now they both
  behave the same.
- The class :class:`gevent.queue.Queue` now supports the :func:`len` function.

.. _future: http://python-future.org
.. _bench_sendall.py: https://raw.githubusercontent.com/gevent/gevent/master/greentest/bench_sendall.py
.. _pypy bug: https://bitbucket.org/pypy/pypy/issues/2091/non-blocking-socketsend-slow-gevent

1.1b2 (Aug 5, 2015)
===================

- Enable using the :mod:`c-ares resolver <gevent.resolver_ares>` under
  PyPy. Note that its performance characteristics are probably
  sub-optimal.
- On some versions of PyPy on some platforms (notably 2.6.0 on 64-bit
  Linux), enabling ``gevent.monkey.patch_builtins`` could cause PyPy
  to crash. Reported in :issue:`618` by Jay Oster.
- :func:`gevent.kill` raises the correct exception in the target greenlet.
  Reported in :issue:`623` by Jonathan Kamens.
- Various fixes on Windows. Reported in :issue:`625`, :issue:`627`,
  and :issue:`628` by jacekt and Yuanteng (Jeff) Pei. Fixed in :pr:`624`.
- Add :meth:`~gevent.fileobject.FileObjectPosix.readable` and
  :meth:`~gevent.fileobject.FileObjectPosix.writable` methods to
  :class:`~gevent.fileobject.FileObjectPosix`; this fixes e.g., help() on Python 3 when
  monkey-patched.

1.1b1 (Jul 17, 2015)
====================

- ``setup.py`` can be run from a directory containing spaces. Reported
  in :issue:`319` by Ivan Smirnov.
- ``setup.py`` can build with newer versions of clang on OS X. They
  enforce the distinction between CFLAGS and CPPFLAGS.
- ``gevent.lock.Semaphore`` is atomic on PyPy, just like it is on
  CPython. This comes at a small performance cost on PyPy.
- Fixed regression that failed to set the ``successful`` value to
  False when killing a greenlet before it ran with a non-default
  exception. Fixed in :pr:`608` by Heungsub Lee.
- libev's child watchers caused :func:`os.waitpid` to become unreliable
  due to the use of signals on POSIX platforms. This was especially
  noticeable when using :mod:`gevent.subprocess` in combination with
  ``multiprocessing``. Now, the monkey-patched ``os`` module provides
  a :func:`~gevent.os.waitpid` function that seeks to ameliorate this. Reported in
  :issue:`600` by champax and :issue:`452` by Łukasz Kawczyński.
- On platforms that implement :class:`select.poll`, provide a
  gevent-friendly :class:`gevent.select.poll` and corresponding
  monkey-patch. Implemented in :pr:`604` by Eddi Linder.
- Allow passing of events to the io callback under PyPy. Reported in
  :issue:`531` by M. Nunberg and implemented in :pr:`604`.
- :func:`gevent.thread.allocate_lock` (and so a monkey-patched standard
  library :func:`~thread.allocate_lock`) more closely matches the behaviour of the
  builtin: an unlocked lock cannot be released, and attempting to do
  so throws the correct exception (``thread.error`` on Python 2,
  ``RuntimeError`` on Python 3). Previously, over-releasing a lock was
  silently ignored. Reported in :issue:`308` by Jędrzej Nowak.
- :class:`gevent.fileobject.FileObjectThread` uses the threadpool to close
  the underling file-like object. Reported in :issue:`201` by
  vitaly-krugl.
- Malicious or malformed HTTP chunked transfer encoding data sent to
  the :class:`pywsgi handler <gevent.pywsgi.WSGIHandler>` is handled more robustly, resulting in
  "HTTP 400 bad request" responses instead of a 500 error or, in the
  worst case, a server-side hang. Reported in :issue:`229` by Björn
  Lindqvist.
- Importing the standard library ``threading`` module *before* using
  ``gevent.monkey.patch_all()`` no longer causes Python 3.4 to fail to
  get the ``repr`` of the main thread, and other CPython platforms to
  return an unjoinable DummyThread. (Note that this is not
  recommended.) Reported in :issue:`153`.
- Under Python 2, use the ``io`` package to implement
  :class:`~gevent.fileobject.FileObjectPosix`. This unifies the code with the Python 3
  implementation, and fixes problems with using ``seek()``. See
  :issue:`151`.
- Under Python 2, importing a module that uses gevent blocking
  functions at its top level from multiple greenlets no longer
  produces import errors (Python 3 handles this case natively).
  Reported in :issue:`108` by shaun and initial fix based on code by
  Sylvain Zimmer.
- :func:`gevent.spawn`, :func:`spawn_raw` and :func:`spawn_later`, as well as the
  :class:`~gevent.Greenlet` constructor, immediately produce useful ``TypeErrors``
  if asked to run something that cannot be run. Previously, the
  spawned greenlet would die with an uncaught ``TypeError`` the first
  time it was switched to. Reported in :issue:`119` by stephan.
- Recursive use of :meth:`ThreadPool.apply
  <gevent.threadpool.ThreadPool.apply>` no longer raises a
  ``LoopExit`` error (using ``ThreadPool.spawn`` and then ``get`` on
  the result still could; you must be careful to use the correct hub).
  Reported in :issue:`131` by 8mayday.
- When the :mod:`threading` module is :func:`monkey-patched
  <gevent.monkey.patch_thread>`, the module-level lock in the
  :mod:`logging` module is made greenlet-aware, as are the instance
  locks of any configured handlers. This makes it safer to import
  modules that use the standard pattern of creating a module-level
  :class:`~logging.Logger` instance before monkey-patching.
  Configuring ``logging`` with a basic configuration and then
  monkey-patching is also safer (but not configurations that involve
  such things as the ``SocketHandler``).
- Fix monkey-patching of :class:`threading.RLock` under Python 3.
- Under Python 3, monkey-patching at the top-level of a module that
  was imported by another module could result in a :exc:`RuntimeError`
  from :mod:`importlib`. Reported in :issue:`615` by Daniel Mizyrycki.
  (The same thing could happen under Python 2 if a ``threading.RLock``
  was held around the monkey-patching call; this is less likely but
  not impossible with import hooks.)
- Fix configuring c-ares for a 32-bit Python when running on a 64-bit
  platform. Reported in :issue:`381` and fixed in :pr:`616` by Chris
  Lane. Additional fix in :pr:`626` by Kevin Chen.
- (Experimental) Let the :class:`pywsgi.WSGIServer` accept a
  :class:`logging.Logger` instance for its ``log`` and (new) ``error_log``
  parameters. Take care that the system is fully monkey-patched very
  early in the process's lifetime if attempting this, and note that
  non-file handlers have not been tested. Fixes :issue:`106`.

1.1a2 (Jul 8, 2015)
===================

- ``gevent.threadpool.ThreadPool.imap`` and ``imap_unordered`` now
  accept multiple iterables.
- (Experimental) Exceptions raised from iterating using the
  ``ThreadPool`` or ``Group`` mapping/application functions should now
  have the original traceback.
- :meth:`gevent.threadpool.ThreadPool.apply` now raises any exception
  raised by the called function, the same as
  :class:`~gevent.pool.Group`/:class:`~gevent.pool.Pool` and the
  builtin :func:`apply` function. This obsoletes the undocumented
  ``apply_e`` function. Original PR :issue:`556` by Robert Estelle.
- Monkey-patch the ``selectors`` module from ``patch_all`` and
  ``patch_select`` on Python 3.4. See :issue:`591`.
- Additional query functions for the :mod:`gevent.monkey` module
  allow knowing what was patched. Discussed in :issue:`135` and
  implemented in :pr:`325` by Nathan Hoad.
- In non-monkey-patched environments under Python 2.7.9 or above or
  Python 3, using a gevent SSL socket could cause the greenlet to
  block. See :issue:`597` by David Ford.
- :meth:`gevent.socket.socket.sendall` supports arbitrary objects that
  implement the buffer protocol (such as ctypes structures), just like
  native sockets. Reported in :issue:`466` by tzickel.
- Added support for the ``onerror`` attribute present in CFFI 1.2.0
  for better signal handling under PyPy. Thanks to Armin Rigo and Omer
  Katz. (See https://bitbucket.org/cffi/cffi/issue/152/handling-errors-from-signal-handlers-in)
- The :mod:`gevent.subprocess` module is closer in behaviour to the
  standard library under Python 3, at least on POSIX. The
  ``pass_fds``, ``restore_signals``, and ``start_new_session``
  arguments are now implemented, as are the ``timeout`` parameters
  to various functions. Under Python 2, the previously undocumented
  ``timeout`` parameter to :meth:`Popen.communicate
  <gevent.subprocess.Popen.communicate>` raises an exception like its
  Python 3 counterpart.
- An exception starting a child process with the :mod:`gevent.subprocess`
  module no longer leaks file descriptors. Reported in :pr:`374` by 陈小玉.
- The example ``echoserver.py`` no longer binds to the standard X11
  TCP port. Reported in :issue:`485` by minusf.
- :func:`gevent.iwait` no longer throws :exc:`~gevent.hub.LoopExit` if the caller
  switches greenlets between return values. Reported and initial patch
  in :issue:`467` by Alexey Borzenkov.
- The default threadpool and default threaded resolver work in a
  forked child process, such as with :class:`multiprocessing.Process`.
  Previously the child process would hang indefinitely. Reported in
  :issue:`230` by Lx Yu.
- Fork watchers are more likely to (eventually) get called in a
  multi-threaded program (except on Windows). See :issue:`154`.
- :func:`gevent.killall` accepts an arbitrary iterable for the greenlets
  to kill. Reported in :issue:`404` by Martin Bachwerk; seen in
  combination with older versions of simple-requests.
- :class:`gevent.local.local` objects are now eligible for garbage
  collection as soon as the greenlet finishes running, matching the
  behaviour of the built-in :class:`threading.local` (when implemented
  natively). Reported in :issue:`387` by AusIV.
- Killing a greenlet (with :func:`gevent.kill` or
  :meth:`gevent.Greenlet.kill`) before it is actually started and
  switched to now prevents the greenlet from ever running, instead of
  raising an exception when it is later switched to. See :issue:`330`
  reported by Jonathan Kamens.

1.1a1 (Jun 29, 2015)
====================

- Add support for Python 3.3 and 3.4. Many people have contributed to
  this effort, including but not limited to Fantix King, hashstat,
  Elizabeth Myers, jander, Luke Woydziak, and others. See :issue:`38`.
- Add support for PyPy. See :issue:`248`. Note that for best results,
  you'll need a very recent PyPy build including CFFI 1.2.0.
- Drop support for Python 2.5. Python 2.5 users can continue to use
  gevent 1.0.x.
- Fix :func:`gevent.joinall` to not ignore ``count`` when
  ``raise_error`` is False. See :pr:`512` by Ivan Diao.
- Fix :class:`gevent.subprocess.Popen` to not ignore the ``bufsize`` argument. Note
  that this changes the (platform dependent) default, typically from
  buffered to unbuffered. See :pr:`542` by Romuald Brunet.
- Upgraded c-ares to 1.10.0. See :pr:`579` by Omer Katz.

  .. caution:: The c-ares ``configure`` script is now more strict about the
               contents of environment variables such as ``CFLAGS`` and ``LDFLAGS``
               and they may have to be modified (for example, ``CFLAGS`` is no
               longer allowed to include ``-I`` directives, which must instead be
               placed in ``CPPFLAGS``).
- Add a ``count`` argument to :func:`gevent.iwait`. See :pr:`482` by
  wiggin15.
- Add a ``timeout`` argument to :meth:`gevent.queue.JoinableQueue.join`
  which now returns whether all items were waited for or not.
- ``gevent.queue.JoinableQueue`` treats ``items`` passed to
  ``__init__`` as unfinished tasks, the same as if they were ``put``.
  Initial :pr:`554` by DuLLSoN.
- ``gevent.pywsgi`` no longer prints debugging information for the
  normal conditions of a premature client disconnect. See :issue:`136`,
  fixed in :pr:`377` by Paul Collier.
- (Experimental.) Waiting on or getting results from greenlets that
  raised exceptions now usually raises the original traceback. This
  should assist things like Sentry to track the original problem. See
  :issue:`450` and :issue:`528` by Rodolfo and Eddi Linder and
  :issue:`240` by Erik Allik.
- Upgrade to libev 4.20. See :pr:`590` by Peter Renström.
- Fix ``gevent.baseserver.BaseServer`` to be printable when its
  ``handle`` function is an instancemethod of itself. See :pr:`501` by Joe
  Jevnik.
- Make the ``acquire`` method of ``gevent.lock.DummySemaphore`` always
  return True, supporting its use-case as an "infinite" or unbounded
  semaphore providing no exclusion, and allowing the idiom ``if
  sem.acquire(): ...``. See :pr:`544` by Mouad Benchchaoui.
- Patch ``subprocess`` by default in ``gevent.monkey.patch_all``. See
  :issue:`446`.
- ``gevent.pool.Group.imap`` and ``imap_unordered`` now accept
  multiple iterables like ``itertools.imap``. :issue:`565` reported by
  Thomas Steinacher.
- *Compatibility note*: ``gevent.baseserver.BaseServer`` and
  its subclass ``gevent.server.StreamServer`` now deterministically
  close the client socket when the request handler returns.
  Previously, the socket was left at the mercies of the garbage
  collector; under CPython 2.x this meant when the last reference went
  away, which was usually, but not necessarily, when the request
  handler returned, but under PyPy it was some arbitrary point in the
  future and under CPython 3.x a ResourceWarning could be generated.
  This was undocumented behaviour, and the client socket could be kept
  open after the request handler returned either accidentally or intentionally.
- *Compatibility note*: ``pywsgi`` now ensures that headers can be
  encoded in latin-1 (ISO-8859-1). This improves adherence to the HTTP
  standard (and is necessary under Python 3). Under certain
  conditions, previous versions could have allowed non-ISO-8859-1
  headers to be sent, but their interpretation by a conforming
  recipient is unknown; now, a UnicodeError will be raised. See :issue:`614`.
