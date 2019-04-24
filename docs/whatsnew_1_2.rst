==========================
 What's new in gevent 1.2
==========================

.. toctree::
   :maxdepth: 2

   changelog_1_2

Detailed information on what has changed is available in
:doc:`changelog_1_2`. This document summarizes the most important changes
since :doc:`gevent 1.1 <whatsnew_1_1>`.

In general, gevent 1.2 is a smaller update than gevent 1.1, focusing
on platform support, standard library compatibility, security, bug
fixes and consistency.

Platform Support
========================

gevent 1.2 supports Python 2.7, 3.4, 3.5 and 3.6 on the CPython
(`python.org`_) interpreter. It also supports `PyPy2`_ 4.0.1 and above
(PyPy2 5.4 or higher is recommended) and PyPy3 5.5.0.


.. caution:: Support for Python 2.6 was removed. Support for Python 3.3 is only
               tested on PyPy3.

.. note:: PyPy is not supported on Windows. (gevent's CFFI backend is not
         available on Windows.)

Python 3.6 was released recently and is supported at the same level as 3.5.

For ease of installation on Windows and OS X, gevent 1.2 is
distributed as pre-compiled binary wheels, in addition to source code.

.. _python.org: http://www.python.org/downloads/
.. _PyPy2: http://pypy.org

Bug Fixes
=========

Since 1.1.2, gevent 1.2 contains over 240 commits from nine different
dozen contributors. About two dozen pull requests were merged.

Improved subprocess support
===========================

In gevent 1.1, subprocess monkey-patching was on by default for the
first time. Over time this led to discovery of a few issues and corner
cases that have been fixed in 1.2.

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
- The :func:`gevent.os.waitpid` function is cooperative in more
  circumstances. Reported in :issue:`878` by Heungsub Lee.

API Additions
=============

Numerous APIs offer slightly expanded functionality in this version.
Look for "changed in version 1.2" or "added in version 1.2" throughout
the documentation for specifics.

Of particular note, several backwards compatible updates to the
subprocess module have been backported from Python 3 to Python 2,
making :mod:`gevent.subprocess` smaller, easier to maintain and in
some cases safer, while letting gevent clients use the updated APIs
even on older versions of Python.

If ``concurrent.futures`` is available (Python 3, or if the Python 2
backport has been installed), then the class
:class:`gevent.threadpool.ThreadPoolExecutor` is defined to create an
executor that always uses native threads, even when the system is
monkey-patched.

Library Updates
===============

The two C libraries that are bundled with gevent have been updated.
libev has been updated from 4.20 to 4.23 (`libev release notes`_) and
c-ares has been updated from 1.10.0 to 1.12.0 (`c-ares release notes`_).


.. _libev release notes: https://github.com/gevent/gevent/blob/master/deps/libev/Changes
.. _c-ares release notes: https://c-ares.haxx.se/changelog.html

Compatibility
=============

This release is intended to be compatible with 1.1.x with no changes
to client source code, so long as only non-deprecated and supported
interfaces were used (as always, internal, non-documented
implementation details may have changed).

In particular the deprecated ``gevent.coros`` module has been removed
and ``gevent.corecext`` and ``gevent.corecffi`` have also been removed.

For security, ``gevent.pywsgi`` no longer accepts incoming headers
containing an underscore, and header values passed to
``start_response`` cannot contain a carriage return or newline. See
:issue:`819` and :issue:`775`, respectively.
