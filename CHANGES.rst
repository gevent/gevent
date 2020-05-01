===========
 Changelog
===========

.. currentmodule:: gevent

.. towncrier release notes start

20.5.0 (2020-05-01)
===================


Features
--------

- Update bundled c-ares to version 1.16.0. `Changes <https://c-ares.haxx.se/changelog.html>`_.
  See :issue:`1588`.
- Update all the bundled ``config.guess`` and ``config.sub`` scripts.
  See :issue:`1589`.
- Update bundled libuv from 1.34.0 to 1.36.0.
  See :issue:`1597`.


Bugfixes
--------

- Use ``ares_getaddrinfo`` instead of a manual lookup.

  This requires c-ares 1.16.0.

  Note that this may change the results, in particular their order.

  As part of this, certain parts of the c-ares extension were adapted to
  use modern Cython idioms.

  A few minor errors and discrepancies were fixed as well, such as
  ``gethostbyaddr('localhost')`` working on Python 3 and failing on
  Python 2. The DNSpython resolver now raises the expected TypeError in
  more cases instead of an AttributeError.
  See :issue:`1012`.
- The c-ares and DNSPython resolvers now raise exceptions much more
  consistently with the standard resolver. Types and errnos are
  substantially more likely to match what the standard library produces.

  Depending on the system and configuration, results may not match
  exactly, at least with DNSPython. There are still some rare cases
  where the system resolver can raise ``herror`` but DNSPython will
  raise ``gaierror`` or vice versa. There doesn't seem to be a
  deterministic way to account for this. On PyPy, ``getnameinfo`` can
  produce results when CPython raises ``socket.error``, and gevent's
  DNSPython resolver also raises ``socket.error``.

  In addition, several other small discrepancies were addressed,
  including handling of localhost and broadcast host names.

  .. note:: This has been tested on Linux (CentOS and Ubuntu), macOS,
            and Windows. It hasn't been tested on other platforms, so
            results are unknown for them. The c-ares support, in
            particular, is using some additional socket functions and
            defines. Please let the maintainers know if this introduces
            issues.
  See :issue:`1459`.


----


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
