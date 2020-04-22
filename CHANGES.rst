===========
 Changelog
===========

.. currentmodule:: gevent

.. towncrier release notes start

20.04.1 (unreleased)
====================

- Nothing changed yet.


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
