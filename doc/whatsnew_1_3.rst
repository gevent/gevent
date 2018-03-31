==========================
 What's new in gevent 1.3
==========================

.. toctree::
   :maxdepth: 2

   changelog

Detailed information on what has changed is available in the
:doc:`changelog`. This document summarizes the most important changes
since :doc:`gevent 1.2 <whatsnew_1_2>`.

.. caution:: This document has not yet been fully updated for gevent 1.3.

gevent 1.3 is an important update for performance, debugging and
monitoring, and platform support. It introduces an (optional) `libuv
<http://libuv.org>`_ loop implementation and supports PyPy on Windows.
See :ref:`gevent-configuration` for information on how to use libuv.

Platform Support
================

gevent 1.3 supports Python 2.7, 3.4, 3.5, 3.6 and 3.7 on the CPython
(`python.org`_) interpreter. It also supports `PyPy2`_ 5.8.0 and above
(PyPy2 5.10 or higher is recommended) and PyPy3 5.10.0.

.. caution:: Python 2.7.8 and below (Python 2.7 without a modern
             ``ssl`` module), is no longer tested or supported. The
             support code remains in this release and gevent can be
             installed on such implementations, but such usage is not
             supported.

.. note:: PyPy is now supported on Windows with the libuv loop implementation.

Python 3.7 is in the process of release right now and gevent is tested
with 3.7b2.

For ease of installation on Windows and OS X, gevent 1.3 is
distributed as pre-compiled binary wheels, in addition to source code.

.. note:: On Linux, you'll need to install gevent from source if you
          wish to use the libuv loop implementation. This is because
          the `manylinux1
          <https://www.python.org/dev/peps/pep-0513/>`_ specification
          for the distributed wheels does not support libuv.

.. _python.org: http://www.python.org/downloads/
.. _PyPy2: http://pypy.org

Bug Fixes
=========

TODO: How many commits and contributors? How many pull requests merged?


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
c-ares has been updated from 1.13.0 to 1.14.0 (`c-ares release notes`_).

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
