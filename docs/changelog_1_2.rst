=================
 Changes for 1.2
=================

.. currentmodule:: gevent

1.2.2 (2017-06-05)
==================

- Testing on Python 3.5 now uses Python 3.5.3 due to SSL changes. See
  :issue:`943`.
- Linux CI has been updated from Ubuntu 12.04 to Ubuntu 14.04 since
  the former has reached EOL.
- Linux CI now tests on PyPy2 5.7.1, updated from PyPy2 5.6.0.
- Linux CI now tests on PyPy3 3.5-5.7.1-beta, updated from PyPy3
  3.3-5.5-alpha.
- Python 2 sockets are compatible with the ``SOCK_CLOEXEC`` flag found
  on Linux. They no longer pass the socket type or protocol to
  ``getaddrinfo`` when ``connect`` is called. Reported in :issue:`944`
  by Bernie Hackett.
- Replace ``optparse`` module with ``argparse``. See :issue:`947`.
- Update to version 1.3.1 of ``tblib`` to fix :issue:`954`,
  reported by ml31415.
- Fix the name of the ``type`` parameter to
  :func:`gevent.socket.getaddrinfo` to be correct on Python 3. This
  would cause callers using keyword arguments to raise a :exc:`TypeError`.
  Reported in :issue:`960` by js6626069. Likewise, correct the
  argument names for ``fromfd`` and ``socketpair`` on Python 2,
  although they cannot be called with keyword arguments under CPython.

  .. note:: The ``gethost*`` functions take different argument names
            under CPython and PyPy. gevent follows the CPython
            convention, although these functions cannot be called with
            keyword arguments on CPython.
- The previously-singleton exception objects ``FileObjectClosed`` and
  ``cancel_wait_ex`` were converted to classes. On Python 3, an
  exception object is stateful, including references to its context
  and possibly traceback, which could lead to objects remaining alive
  longer than intended.
- Make sure that ``python -m gevent.monkey <script>`` runs code in the
  global scope, not the scope of the ``main`` function. Fixed in
  :pr:`975` by Shawn Bohrer.

1.2.1 (2017-01-12)
==================

- CI services now test on 3.6.0.
- Windows: Provide ``socket.socketpair`` for all Python 3 versions.
  This was added to Python 3.5, but tests were only added in 3.6.
  (For versions older than 3.4 this is a gevent extension.) Previously
  this was not supported on any Python 3 version.
- Windows: List ``subprocess.STARTUPINFO`` in ``subprocess.__all__``
  for 3.6 compatibility.
- The ``_DummyThread`` objects created by calling
  :func:`threading.current_thread` from inside a raw
  :class:`greenlet.greenlet` in a system with monkey-patched
  ``threading`` now clean up after themselves when the
  greenlet dies (:class:`gevent.Greenlet`-based ``_DummyThreads`` have
  always cleaned up). This requires the use of a :class:`weakref.ref`
  (and may not be timely on PyPy).
  Reported in :issue:`918` by frozenoctobeer.
- Build OS X wheels with ``-D_DARWIN_FEATURE_CLOCK_GETTIME=0`` for
  compatibility with OS X releases before 10.12 Sierra. Reported by
  Ned Batchelder in :issue:`916`.

1.2.0 (2016-12-23)
==================

- The c-ares DNS resolver ignores bad flags to getnameinfo, like the
  system resolver does. Discovered when cleaning up the DNS resolver
  tests to produce more reliable results. See :issue:`774`.

1.2a2 (Dec 9, 2016)
===================

- Update libev to version 4.23.
- Allow the ``MAKE`` environment variable to specify the make command
  on non-Windows systems for ease of development on BSD systems where
  ``make`` is BSD make and ``gmake`` is GNU make (gevent requires GNU
  make). See :issue:`888`.
- Let :class:`gevent.server.StreamServer` accept an ``SSLContext`` on
  Python versions that support it. Added in :pr:`904` by Arcadiy Ivanov.

1.2a1 (Oct 27, 2016)
====================

Incompatible Changes
--------------------
- Support for Python 2.6 has been removed. See :pr:`766`.
- Remove module ``gevent.coros`` which was replaced by ``gevent.lock``
  and has been deprecated since 1.0b2.
- The internal implementation modules ``gevent.corecext`` and
  ``gevent.corecffi`` have been moved. Please import from
  ``gevent.core`` instead; this has always been the only documented place to
  import from.

Libraries and Installation
--------------------------

- Update libev to version 4.22 (was 4.20).
- Update tblib to 1.3.0.
- Update Cython to 0.25 (was 0.23.5).
- Update c-ares to version 1.12.0 (was 1.10.0) (`release notes <https://c-ares.haxx.se/changelog.html>`_).
- For the benefit of downstream package maintainers, gevent is now
  tested with c-ares and libev linked dynamically and not embedded
  (i.e., using the system libraries). However, only the versions
  shipped with gevent are tested and known to work.
- The repository directory layout has been changed to make it easier
  to include third-party dependencies. Likewise, the setup.py script
  has been split to make it easier to build third-party dependencies.
- PyPy/CFFI: The corecffi native extension is now only built at
  installation time. Previously, if it wasn't available, a build was
  attempted at every import. This could lead to scattered "gevent"
  directories and undependable results.
- setuptools is now required at build time on all platforms.
  Previously it was only required for Windows and PyPy.
- POSIX: Don't hardcode ``/bin/sh`` into the configuration command
  line, instead relying on ``sh`` being on the ``PATH``, as
  recommended by `the standard <http://pubs.opengroup.org/onlinepubs/9699919799/utilities/sh.html>`_.
  Fixed in :pr:`809` by Fredrix Fornwall.

Security
--------
- :mod:`gevent.pywsgi` now checks that the values passed to
  ``start_response`` do not contain a carriage return or newline in
  order to prevent HTTP response splitting (header injection), raising
  a :exc:`ValueError` if they do. See :issue:`775`.
- Incoming headers containing an underscore are no longer placed in
  the WSGI environ. See :issue:`819`.
- Errors logged by :class:`~gevent.pywsgi.WSGIHandler` no
  longer print the entire WSGI environment by default. This avoids
  possible information disclosure vulnerabilities. Applications can
  also opt-in to a higher security level for the WSGI environment if they
  choose and their frameworks support it. Originally reported
  in :pr:`779` by sean-peters-au and changed in :pr:`781`.

Platforms
---------

- As mentioned above, Python 2.6 is no longer supported.
- Python 3.6 is now tested on POSIX platforms. This includes a few
  notable changes:

  * SSLContext.wrap_socket accepts the ``session`` parameter, though
    this parameter isn't useful prior to 3.6.
  * SSLSocket.recv(0) or read(0) returns an empty byte string. This is
    a fix for `Python bug #23804 <http://bugs.python.org/issue23804>`_
    which has also been merged into Python 2.7 and Python 3.5.
- PyPy3 5.5.0 *alpha* (supporting Python 3.3.5) is now tested and passes the
  test suite. Thanks to btegs for :issue:`866`, and Fabio Utzig for :pr:`826`.
  Note that PyPy3 is not optimized for performance either by the PyPy
  developers or under gevent, so it may be significantly slower than PyPy2.

Stdlib Compatibility
--------------------
- The modules :mod:`gevent.os`, :mod:`gevent.signal` and
  :mod:`gevent.select` export all the attributes from their
  corresponding standard library counterpart.
- Python 2: ``reload(site)`` no longer fails with a ``TypeError`` if
  gevent has been imported. Reported in :issue:`805` by Jake Hilton.
- Python 2: ``sendall`` on a non-blocking socket could spuriously fail
  with a timeout.

select/poll
~~~~~~~~~~~

- If :func:`gevent.select.select` is given a negative *timeout*
  argument, raise an exception like the standard library does.
- If :func:`gevent.select.select` is given closed or invalid
  file descriptors in any of its lists, raise the appropriate
  ``EBADF`` exception like the standard library does. Previously,
  libev would tend to return the descriptor as ready. In the worst
  case, this adds an extra system call, but may also reduce latency if
  descriptors are ready at the time of entry.
- :class:`selectors.SelectSelector` is properly monkey-patched
  regardless of the order of imports. Reported in :issue:`835` by
  Przemysław Węgrzyn.
- :meth:`gevent.select.poll.unregister` raises an exception if *fd* is not
  registered, like the standard library.
- :meth:`gevent.select.poll.poll` returns an event with
  ``POLLNVAL`` for registered fds that are invalid. Previously it
  would tend to report both read and write events.


File objects
~~~~~~~~~~~~

- ``FileObjectPosix`` exposes the ``read1`` method when in read mode,
  and generally only exposes methods appropriate to the mode it is in.
- ``FileObjectPosix`` supports a *bufsize* of 0 in binary write modes.
  Reported in :issue:`840` by Mike Lang.
- Python 3: :meth:`gevent.socket.connect_ex` was letting
  ``BlockingIOError`` (and possibly others) get raised instead of
  returning the errno due to the refactoring of the exception
  hierarchy in Python 3.3. Now the errno is returned. Reported in
  :issue:`841` by Dana Powers.


Other Changes
-------------

- :class:`~.Group` and :class:`~.Pool` now return whether
  :meth:`~.Group.join` returned with an empty group. Suggested by Filippo Sironi in
  :pr:`503`.
- Unhandled exception reports that kill a greenlet now include a
  timestamp. See :issue:`137`.
- :class:`~.PriorityQueue` now ensures that an initial items list is a
  valid heap. Fixed in :pr:`793` by X.C.Dong.
- :class:`gevent.hub.signal` (aka :func:`gevent.signal`) now verifies
  that its `handler` argument is callable, raising a :exc:`TypeError`
  if it isn't. Reported in :issue:`818` by Peter Renström.
- If ``sys.stderr`` has been monkey-patched (not recommended),
  exceptions that the hub reports aren't lost and can still be caught.
  Reported in :issue:`825` by Jelle Smet.
- The :func:`gevent.os.waitpid` function is cooperative in more
  circumstances. Reported in :issue:`878` by Heungsub Lee.
- The various ``FileObject`` implementations are more consistent with
  each other. **Note:** Writing to the *io* property of a FileObject should be
  considered deprecated.
- Timeout exceptions (and other asynchronous exceptions) could cause
  the BackdoorServer to fail to properly manage the
  stdout/stderr/stdin values. Reported with a patch in :pr:`874` by
  stefanmh.
- The BackDoorServer now tracks spawned greenlets (connections) and
  kills them in its ``stop`` method.

Servers
~~~~~~~
- Default to AF_INET6 when binding to all addresses (e.g.,
  ""). This supports both IPv4 and IPv6 connections (except on
  Windows). Original change in :pr:`495` by Felix Kaiser.
- pywsgi/performance: Chunks of data the application returns are no longer copied
  before being sent to the socket when the transfer-encoding is
  chunked, potentially reducing overhead for large responses.

Threads
~~~~~~~
- Add :class:`gevent.threadpool.ThreadPoolExecutor` (a
  :class:`concurrent.futures.ThreadPoolExecutor` variant that always
  uses native threads even when the system has been monkey-patched)
  on platforms that have ``concurrent.futures``
  available (Python 3 and Python 2 with the ``futures`` backport
  installed). This is helpful for, e.g., grpc. Reported in
  :issue:`786` by Markus Padourek.
- Native threads created before monkey-patching threading can now be
  joined. Previously on Python < 3.4, doing so would raise a
  ``LoopExit`` error. Reported in :issue:`747` by Sergey Vasilyev.

SSL
~~~
- On Python 2.7.9 and above (more generally, when the SSL backport is
  present in Python 2), :func:`gevent.ssl.get_server_certificate`
  would raise a :exc:`ValueError` if the system wasn't monkey-patched.
  Reported in :issue:`801` by Gleb Dubovik.
- On Python 2.7.9 and Python 3, closing an SSL socket in one greenlet
  while it's being read from or written to in a different greenlet is
  less likely to raise a :exc:`TypeError` instead of a
  :exc:`ValueError`. Reported in :issue:`800` by Kevin Chen.


subprocess module
~~~~~~~~~~~~~~~~~

- Setting SIGCHLD to SIG_IGN or SIG_DFL after :mod:`gevent.subprocess`
  had been used previously could not be reversed, causing
  ``Popen.wait`` and other calls to hang. Now, if SIGCHLD has been
  ignored, the next time :mod:`gevent.subprocess` is used this will be
  detected and corrected automatically. (This potentially leads to
  issues with :func:`os.popen` on Python 2, but the signal can always
  be reset again. Mixing the low-level process handling calls,
  low-level signal management and high-level use of
  :mod:`gevent.subprocess` is tricky.) Reported in :issue:`857` by
  Chris Utz.
- ``Popen.kill`` and ``send_signal`` no longer attempt to send signals
  to processes that are known to be exited.

Several backwards compatible updates to the subprocess module have
been backported from Python 3 to Python 2, making
:mod:`gevent.subprocess` smaller, easier to maintain and in some cases
safer.

- Popen objects can be used as context managers even on Python 2. The
  high-level API functions (``call``, etc) use this for added safety.
- The :mod:`gevent.subprocess` module now provides the
  :func:`gevent.subprocess.run` function in a cooperative way even
  when the system is not monkey patched, on all supported versions of
  Python. (It was added officially in Python 3.5.)
- Popen objects save their *args* attribute even on Python 2.
- :exc:`gevent.subprocess.TimeoutExpired` is defined even on Python 2,
  where it is a subclass of the :exc:`gevent.timeout.Timeout`
  exception; all instances where a ``Timeout`` exception would
  previously be thrown under Python 2 will now throw a
  ``TimeoutExpired`` exception.
- :func:`gevent.subprocess.call` (and ``check_call``) accepts the
  *timeout* keyword argument on Python 2. This is standard on Python
  3, but a gevent extension on Python 2.
- :func:`gevent.subprocess.check_output` accepts the *timeout* and
  *input* arguments on Python 2. This is standard on Python 3, but a
  gevent extension on Python 2.
