==========================
 What's new in gevent 1.3
==========================

Detailed information on what has changed is available in the
:doc:`changelog`. This document summarizes the most important changes
since :doc:`gevent 1.2 <whatsnew_1_2>`.

.. caution:: This document has not yet been updated for gevent 1.3.

In general, gevent 1.2 is a smaller update than gevent 1.1, focusing
on platform support, standard library compatibility, security, bug
fixes and consistency.

Platform Support
================

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

New Pure-Python DNS Resolver
============================

WRITE ME.

API Additions
=============

Numerous APIs offer slightly expanded functionality in this version.
Look for "changed in version 1.3" or "added in version 1.3" throughout
the documentation for specifics.


Library Updates
===============

One of the C libraries that are bundled with gevent have been updated.
c-ares has been updated from 1.12.0 to 1.13.0 (`c-ares release notes`_).


.. _c-ares release notes: https://c-ares.haxx.se/changelog.html

Compatibility
=============

This release is intended to be compatible with 1.2.x with no changes
to client source code, so long as only non-deprecated and supported
interfaces were used (as always, internal, non-documented
implementation details may have changed).

The :doc:`resolvers <dns>` have been refactored. As a result,
``gevent.ares``, ``gevent.resolver_ares`` and
``gevent.resolver_thread`` have been deprecated. Choosing a resolver
by alias (e.g., 'thread') in the ``GEVENT_RESOLVER`` environment
variable continues to work as before.

TODO: Remove deprecated gevent.wsgi package.
