==========================
 What's new in gevent 1.1
==========================

Detailed information an what has changed is available in the
:doc:`changelog`. This document summarizes the most important changes
since gevent 1.0.2.

Platform Support
================

gevent 1.1 supports Python 2.6, 2.7, 3.3, and 3.4 on the CPython
(`python.org`_) interpreter. It also supports `PyPy`_ 2.6.1 and above (with
best results being obtained on PyPy 4.0.1 and above); PyPy3 is not
supported.

Support for Python 2.5 was removed when support for Python 3 was
added. Any further releases in the 1.0.x line will maintain support
for Python 2.5.

Python 3.5 has preliminary support, which means that gevent is
expected to generally run and function with the same level of support
as on Python 3.4, but new features and APIs introduced in 3.5 may not
be properly supported (e.g., `DevpollSelector`_) and due to the recent
arrival of Python 3.5, the level of testing it has received is lower.

For ease of installation on Windows and OS X, gevent 1.1 is
distributed as pre-compiled binary wheels, in addition to source code.

.. _python.org: http://www.python.org/downloads/
.. _PyPy: http://pypy.org
.. _DevpollSelector: https://docs.python.org/3.5/whatsnew/3.5.html#selectors

PyPy Notes
----------

PyPy has been tested on OS X and 64-bit Linux from version 2.6.1
through 4.0.0 and 4.0.1.

.. note:: PyPy is not supported on Windows. (gevent's CFFI backend is not
          available on Windows.)

- Version 2.6.1 or above is required for proper signal handling. Prior
  to 2.6.1 and its inclusion of `cffi 1.3.0`_, signals could be
  delivered incorrectly or fail to be delivered during a blocking
  operation. (PyPy 2.5.0 includes CFFI 0.8.6 while 2.6.0 has 1.1.0;
  the necessary feature was added in `1.2.0`_ which is not itself
  directly present in any PyPy release.) CFFI 1.3.0 also allows using
  the CFFI backend on CPython.
- Overall performance seems to be quite acceptable with newer versions
  of PyPy. The benchmarks distributed with gevent typically perform as
  well or better on PyPy than on CPython at least on some platforms.
  Things that are known or expected to be (relatively) slower under
  PyPy include the :mod:`c-ares resolver <gevent.resolver_ares>` and
  :class:`~gevent.lock.Semaphore`. Whether or not these matter will
  depend on the workload of each application.

.. caution:: The ``c-ares`` resolver is considered highly experimental
             under PyPy and is not recommended for production use.
             Released versions of PyPy through at least 4.0.1 have `a
             bug`_ that can cause a memory leak when subclassing
             objects that are implemented in Cython, as is the c-ares
             resolver. In addition, thanks to reports like
             :issue:`704`, we know that the PyPy garbage collector can
             interact badly with Cython-compiled code, leading to
             crashes. While the intended use of the ares resolver has
             been loosely audited for these issues, no guarantees are made.

.. note:: PyPy 4.0.x on Linux is known to *rarely* (once per 24 hours)
          encounter crashes when running heavily loaded, heavily
          networked gevent programs (even without ``c-ares``). The
          exact cause is unknown and is being tracked in :issue:`677`.

.. _cffi 1.3.0: https://bitbucket.org/cffi/cffi/src/ad3140a30a7b0ca912185ef500546a9fb5525ece/doc/source/whatsnew.rst?at=default
.. _1.2.0: https://cffi.readthedocs.org/en/latest/whatsnew.html#v1-2-0
.. _a bug: https://bitbucket.org/pypy/pypy/issues/2149/memory-leak-for-python-subclass-of-cpyext

Improved subprocess support
===========================

In gevent 1.0, support and monkey patching for the :mod:`subprocess`
module was added. Monkey patching this module was off by default.

In 1.1, monkey patching ``subprocess`` is on by default due to
improvements in handling child processes and requirements by
downstream libraries, notably `gunicorn`_.

- :func:`gevent.os.fork`, which is monkey patched by default (and
  should be used to fork a gevent-aware process that expects to use
  gevent in the child process) has been improved and cooperates with
  :func:`gevent.os.waitpid` (again monkey patched by default) and
  :func:`gevent.signal.signal` (which is monkey patched only for the
  :data:`signal.SIGCHLD` case). The latter two patches are new in 1.1.
- Fork-watchers will be called, even in multi-threaded programs
  (except on Windows).
- The default threadpool and threaded resolver work in child
  processes.
- File descriptors are no longer leaked if
  :class:`gevent.subprocess.Popen` fails to start the child.

In addition, simple use of :class:`multiprocessing.Process` is now
possible in a monkey patched system, at least on POSIX platforms.

.. caution:: Use of :class:`multiprocessing.Queue` when :mod:`thread`
             has been monkey-patched will lead to a hang due to
             ``Queue``'s internal use of a blocking pipe and threads. For the same
             reason, :class:`concurrent.futures.ProcessPoolExecutor`,
             which internally uses a ``Queue``, will hang.

.. caution:: It is not possible to use :mod:`gevent.subprocess` from
             native threads. See :mod:`gevent.subprocess` for details.

.. tip:: All of the above entail forking a child process. Forking
		 a child process that uses gevent, greenlets, and libev
		 can have some unexpected consequences if the child
		 doesn't immediately ``exec`` a new binary. Be sure you
		 understand these consequences before using this
		 functionality, especially late in a program's lifecycle.
		 For a more robust solution to certain uses of child
		 process, consider `gipc`_.

.. _gunicorn: http://gunicorn.org
.. _gipc: https://gehrcke.de/gipc/

Monkey patching
===============

Monkey patching is more robust, especially if the standard library
:mod:`threading` or :mod:`logging` modules had been imported before
applying the patch. In addition, there are now supported ways to
determine if something has been monkey patched.

API Additions
=============

Numerous APIs offer slightly expanded functionality in this version. Highlights
include:

- A gevent-friendly version of :obj:`select.poll` (on platforms that
  implement it).
- :class:`~gevent.fileobject.FileObjectPosix` uses the :mod:`io`
  package on both Python 2 and Python 3, increasing its functionality,
  correctness, and performance. (Previously, the Python 2 implementation used the
  undocumented class :class:`socket._fileobject`.)
- Locks raise the same error as standard library locks if they are
  over-released.
- :meth:`ThreadPool.apply <gevent.threadpool.ThreadPool.apply>` can
  now be used recursively.
- The various pool objects (:class:`~gevent.pool.Group`,
  :class:`~gevent.pool.Pool`, :class:`~gevent.threadpool.ThreadPool`)
  support the same improved APIs: :meth:`imap <gevent.pool.Group.imap>`
  and :meth:`imap_unordered <gevent.pool.Group.imap_unordered>` accept
  multiple iterables, :meth:`apply <gevent.pool.Group.apply>` raises any exception raised by the
  target callable, etc.
- Killing a greenlet (with :func:`gevent.kill` or
  :meth:`Greenlet.kill <gevent.Greenlet.kill>`) before it is actually started and
  switched to now prevents the greenlet from ever running, instead of
  raising an exception when it is later switched to. Attempting to
  spawn a greenlet with an invalid target now immediately produces
  a useful :exc:`TypeError`, instead of spawning a greenlet that would
  (usually) immediately die the first time it was switched to.
- Almost anywhere that gevent raises an exception from one greenlet to
  another (e.g., :meth:`Greenlet.get <gevent.Greenlet.get>`),
  the original traceback is preserved and raised.
- The WSGI server found in :mod:`gevent.pywsgi` is more robust against
  errors in either the client or the WSGI application, fixing several
  hangs or HTTP protocol violations. It also supports new
  functionality such as configurable error handling and logging.

Library Updates
===============

The two C libraries that are bundled with gevent have been updated.
libev has been updated from 4.19 to 4.20 (`libev release notes`_) and
c-ares has been updated from 1.9.1 to 1.10.0 (`c-ares release notes`_).

.. caution:: The c-ares ``configure`` script is now *much* stricter
             about the contents of compilation environment variables
             such as ``$CFLAGS`` and ``$LDFLAGS``. For example,
             ``$CFLAGS`` is no longer allowed to contain ``-I``
             directives; instead, these must be placed in
             ``$CPPFLAGS``. That's one common cause of an error
             like the following when compiling from scratch on a POSIX
             platform::

                 Running '(cd  "/tmp/easy_install-NT921u/gevent-1.1b2/c-ares"  && if [ -e ares_build.h ]; then cp ares_build.h ares_build.h.orig; fi   && /bin/sh ./configure CONFIG_COMMANDS= CONFIG_FILES=   && cp ares_config.h ares_build.h "$OLDPWD"   && mv ares_build.h.orig ares_build.h) > configure-output.txt' in /tmp/easy_install-NT921u/gevent-1.1b2/build/temp.linux-x86_64-2.7/c-ares
                 configure: error: Can not continue. Fix errors mentioned immediately above this line.

.. _libev release notes: https://github.com/gevent/gevent/blob/master/libev/Changes#L17
.. _c-ares release notes: https://raw.githubusercontent.com/bagder/c-ares/cares-1_10_0/RELEASE-NOTES

Compatibility
=============

This release is intended to be compatible with 1.0.x with minimal or
no changes to client source code. However, there are a few changes to
be aware of that might affect some applications. Most of these changes
are due to the increased platform support of Python 3 and PyPy and
reduce the cases of undocumented or non-standard behaviour.

- :class:`gevent.baseserver.BaseServer` deterministically
  `closes its sockets <https://github.com/gevent/gevent/issues/248#issuecomment-82467350>`_.

  As soon as a request completes (the request handler returns),
  the ``BaseServer`` and its subclasses including
  :class:`gevent.server.StreamServer` and
  :class:`gevent.pywsgi.WSGIServer` close the client socket.

  In gevent 1.0, the client socket was left to the mercies of the
  garbage collector (this was undocumented). In the typical case, the
  socket would still be closed as soon as the request handler returned
  due to CPython's reference-counting garbage collector. But this
  meant that a reference cycle could leave a socket dangling open for
  an indeterminate amount of time, and a reference leak would result
  in it never being closed. It also meant that Python 3 would produce
  ResourceWarnings, and PyPy (which, unlike CPython, `does not use a
  reference-counted GC`_) would only close (and flush!) the socket at
  an arbitrary time in the future.

  If your application relied on the socket not being closed when the
  request handler returned (e.g., you spawned a greenlet that
  continued to use the socket) you will need to keep the request
  handler from returning (e.g., ``join`` the greenlet). If for some
  reason that isn't possible, you may subclass the server to prevent
  it from closing the socket, at which point the responsibility for
  closing and flushing the socket is now yours; *but* the former
  approach is strongly preferred, and subclassing the server for this
  reason may not be supported in the future.

.. _does not use a reference-counted GC: http://doc.pypy.org/en/latest/cpython_differences.html#differences-related-to-garbage-collection-strategies

- :class:`gevent.pywsgi.WSGIServer` ensures that headers and the
  status line set by the application can be encoded in the ISO-8859-1
  (Latin-1) charset and are of the *native string type*.

  Under gevent 1.0, non-``bytes`` headers (that is, ``unicode``, since
  gevent 1.0 only ran on Python 2) were encoded according to the
  current default Python encoding. In some cases, this could allow
  non-Latin-1 characters to be sent in the headers, but this violated
  the HTTP specification, and their interpretation by the recipient is
  unknown. In other cases, gevent could send malformed partial HTTP
  responses. Now, a :exc:`UnicodeError` will be raised proactively.

  Most applications that adhered to the WSGI PEP, :pep:`3333`, will not
  need to make any changes. See :issue:`614` for more discussion.


- Under Python 2, the previously undocumented ``timeout`` parameter to
  :meth:`Popen.wait <gevent.subprocess.Popen.wait>` (a gevent extension
  ) now throws an exception, just like the documented parameter to the
  same stdlib method in Python 3.

- The previously undocumented class
  ``gevent.fileobject.SocketAdapter`` has been removed.
