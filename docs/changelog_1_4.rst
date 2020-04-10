===========
 Changelog
===========

.. currentmodule:: gevent


1.4.0 (2019-01-04)
==================

- Build with Cython 0.29 in '3str' mode.

- Test with PyPy 6.0 on Windows.

- Add support for application-wide callbacks when ``Greenlet`` objects
  are started. See :pr:`1289`, provided by Yury Selivanov.

- Fix consuming a single ready object using
  ``next(gevent.iwait(objs))``. Previously such a construction would
  hang because `iter` was not called. See :pr:`1288`, provided by Josh
  Snyder. This is not recommended, though, as unwaited objects will
  have dangling links (but see next item).

- Make `gevent.iwait` return an iterator that can now also be used as
  a context manager. If you'll only be consuming part of the iterator,
  use it in a ``with`` block to avoid leaking resources. See
  :pr:`1290`, provided by Josh Snyder.

- Fix semaphores to immediately notify links if they are ready and
  ``rawlink()`` is called. This behaves like ``Event`` and
  ``AsyncEvent``. Note that the order in which semaphore links are
  called is not specified. See :issue:`1287`, reported by Dan Milon.

- Improve safety of handling exceptions during interpreter shutdown.
  See :issue:`1295` reported by BobDenar1212.

- Remove the deprecated ability to specify ``GEVENT_RESOLVER`` and
  other importable settings as a ``path/to/a/package.module.item``.
  This had race conditions and didn't work with complicated resolver
  implementations. Place the required package or module on `sys.path`
  first.

- Reduce the chances that using the blocking monitor functionality
  could result in apparently random ``SystemError:
  Objects/tupleobject.c: bad argument to internal function``. Reported
  in :issue:`1302` by Ulrich Petri.

- Refactored the gevent test runner and test suite to make them more
  reusable. In particular, the tests are now run with ``python -m
  gevent.tests``. See :issue:`1293`.

- Make a monkey-patched ``socket.getaddrinfo`` return socket module
  enums instead of plain integers for the socket type and address
  family on Python 3. See :issue:`1310` reported by TheYOSH.

  .. note:: This requires Python 3.4.3 or above due to an undocumented
            change in that version.

- Make gevent's pywsgi server set the non-standard environment value
  ``wsgi.input_terminated`` to True. See :issue:`1308`.

- Make `gevent.util.assert_switches` produce more informative messages
  when the assertion fails.

- Python 2: If a `gevent.socket` was closed asynchronously (in a
  different greenlet or a hub callback), `AttributeError` could result
  if the socket was already in use. Now the correct socket.error
  should be raised.

- Fix :meth:`gevent.threadpool.ThreadPool.join` raising a
  `UserWarning` when using the libuv backend. Reported in
  :issue:`1321` by ZeroNet.

- Fix ``FileObjectPosix.seek`` raising `OSError` when it should have
  been `IOError` on Python 2. Reported by, and PR by, Ricardo Kirkner.
  See :issue:`1323`.

- Upgrade libuv from 1.23.2 to 1.24.0.
