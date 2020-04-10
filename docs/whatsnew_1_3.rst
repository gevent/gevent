==========================
 What's new in gevent 1.3
==========================

.. currentmodule:: gevent

.. toctree::
   :maxdepth: 2

   changelog_1_3

Detailed information on what has changed is available in the
:doc:`changelog`. This document summarizes the most important changes
since :doc:`gevent 1.2 <whatsnew_1_2>`.

gevent 1.3 is an important update for performance, debugging and
monitoring, and platform support. It introduces an (optional) `libuv
<http://libuv.org>`_ loop implementation and supports PyPy on Windows.
See :doc:`loop_impls` for more.

Since gevent 1.2.2 there have been about 450 commits from a half-dozen
contributors. Almost 100 pull requests and more than 100 issues have
been closed.

Platform Support
================

gevent 1.3 supports Python 2.7, 3.4, 3.5, 3.6 and 3.7 on the CPython
(`python.org`_) interpreter. It also supports `PyPy2`_ 5.8.0 and above
(PyPy2 5.10 or higher is recommended) and PyPy3 5.10.0.

.. caution::

   Python 2.7.8 and below (Python 2.7 without a modern
   ``ssl`` module), is no longer tested or supported. The
   support code remains in this release and gevent can be
   installed on such implementations, but such usage is not
   supported. Support for Python 2.7.8 will be removed in the next
   major version of gevent.

.. note::

   PyPy is now supported on Windows with the libuv loop
   implementation.

Python 3.7 is in the process of release right now and gevent is tested
with 3.7b4, the last scheduled beta for Python 3.7.

For ease of installation on Windows, OS X and Linux, gevent 1.3 is
distributed as pre-compiled binary wheels, in addition to source code.

.. note::

   On Linux, you'll need to install gevent from source if you wish to
   use the libuv loop implementation. This is because the `manylinux1
   <https://www.python.org/dev/peps/pep-0513/>`_ specification for the
   distributed wheels does not support libuv. The CFFI library *must*
   be installed at build time.

.. _python.org: http://www.python.org/downloads/
.. _PyPy2: http://pypy.org

Greenlet Attributes
===================

:class:`Greenlet` objects have gained some useful new
attributes:

- :attr:`Greenlet.spawning_greenlet` is the greenlet that created this
  greenlet. Since the ``parent`` of a greenlet is almost always gevent's
  :class:`hub <gevent.hub.Hub>`, this can be more
  useful to understand greenlet relationships.
- :attr:`Greenlet.spawn_tree_locals` is a dictionary of values
  maintained through the spawn tree (i.e., all descendents of a
  particular greenlet based on ``spawning_greenlet``). This is
  convenient to share values between a set of greenlets, for example,
  all those involved in processing a request.
- :attr:`Greenlet.spawning_stack` is a :obj:`frame <types.FrameType>` -like object that
  captures where the greenlet was created and can be passed to :func:`traceback.print_stack`.
- :attr:`Greenlet.minimal_ident` is a small integer unique across all
  greenlets.
- :attr:`Greenlet.name` is a string printed in the greenlet's repr by default.

"Raw" greenlets created with `spawn_raw` default to having the
``spawning_greenlet`` and ``spawn_tree_locals``.

This extra data is printed by the new
:func:`gevent.util.print_run_info` function.

Performance
===========

gevent 1.3 uses Cython on CPython to compile several performance
critical modules. As a result, overall performance is improved.
Specifically, queues are up to 5 times faster, pools are 10-20%
faster, and the :class:`gevent.local.local` is up to 40 times faster.
See :pr:`1156`, :pr:`1155`, :pr:`1117` and :pr:`1154`.


Better Behaved Callbacks
========================

In gevent 1.2.2, event loop callbacks (including things like
``sleep(0)``) would be run in sequence until we ran them all, or until
we ran 10,000. Simply counting the number of callbacks could lead to
no IO being serviced for an arbitrary, unbound, amount of time. To
correct this, gevent 1.3 introduces `gevent.getswitchinterval` and
will run callbacks for only (approximately) that amount of time before
checking for IO. (This is similar to the way that Python 2 counted
bytecode instructions between thread switches but Python 3 uses the
more deterministic timer approach.) The hope is that this will result
in "smoother" application behaviour and fewer pitfalls. See
:issue:`1072` for more details.

Monitoring and Debugging
========================

Many of the new greenlet attributes are useful for monitoring and
debugging gevent applications. gevent also now has the (optional)
ability to monitor for greenlets that call blocking functions and
stall the event loop and to periodically check if the application has
exceeded a configured memory limit. See :doc:`monitoring` for more
information.


New Pure-Python DNS Resolver
============================

The `dnspython <https://pypi.org/project/dnspython>`_ library is a
new, pure-Python option for :doc:`/dns`. Benchmarks show it to be
faster than the existing c-ares resolver and it is also more stable on
PyPy. The c-ares resolver may be deprecated and removed in the future.

API Additions
=============

Numerous APIs offer slightly expanded functionality in this version.
Look for "changed in version 1.3" or "added in version 1.3" throughout
the documentation for specifics.

A few changes of note:

- The low-level watcher objects now have a
  :func:`~gevent._interfaces.IWatcher.close` method that *must* be
  called to promptly dispose of native (libev or libuv) resources.
- `gevent.monkey.patch_all` defaults to patching ``Event``.
- `gevent.subprocess.Popen` accepts the same keyword arguments in
  Python 2 as it does in Python 3.
- `gevent.monkey.patch_all` and the various individual patch
  functions, emit events as patching is being done. This can be used
  to extend the patching process for new modules. ``patch_all`` also
  passes all unknown keyword arguments to these events. See
  :pr:`1169`.
- The module :mod:`gevent.events` contains the events that parts of
  gevent can emit. It will use :mod:`zope.event` if that is installed.

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
implementation details may have changed). Here are some specific
compatibility notes.

- The :doc:`resolvers <dns>` have been refactored. As a result,
  ``gevent.ares``, ``gevent.resolver_ares`` and
  ``gevent.resolver_thread`` have been deprecated. Choosing a resolver
  by alias (e.g., 'thread') in the ``GEVENT_RESOLVER`` environment
  variable continues to work as before.

- The internal module ``gevent._threading`` was significantly
  refactored. As the name indicates this is an internal module not
  intended as part of the public API, but such uses have been observed.

- The module ``gevent.wsgi`` was removed. Use :mod:`gevent.pywsgi`
  instead. ``gevent.wsgi`` was nothing but an alias for
  :mod:`gevent.pywsgi` since gevent 1.0a1 (2011).

..  LocalWords:  Greenlet
