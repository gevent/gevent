==========================
 What's new in gevent 1.5
==========================

.. currentmodule:: gevent

.. toctree::
   :maxdepth: 2

   changelog_1_5

Detailed information on what has changed is available in the
:doc:`changelog`. This document summarizes the most important changes
since :doc:`gevent 1.4 <whatsnew_1_4>`.

gevent 1.5 is a maintenance and feature release including bug fixes and a
number of API improvements.

Versioning
==========

Future releases of gevent will use a scheme similar to `CalVer
<https://calver.org>`_. See :doc:`development/release_process` for information
on future deprecations and feature removals.

Platform Support
================

gevent 1.5 drops support for Python 3.4, and drops support for PyPy
< 7. It also adds official support for Python 3.8.

gevent is tested with CPython 2.7.17, 3.5.9, 3.6.10, 3.7.7, 3.8.2,
PyPy 2 7.3.0 and PyPy3 7.3.0.

.. caution:: Older releases, such as RHEL 5, are no longer supported.

Packaging Changes
=================

gevent now distributes `manylinux2010
<https://www.python.org/dev/peps/pep-0571/>`_ binary wheels for Linux,
instead of the older ``manylinux1`` standard. This updated platform
tag allows gevent to distribute libuv support by default. CentOS 6 is
the baseline for this tag.

gevent bundles a ``pyproject.toml`` now. This is useful for building
from source.

.. caution::

   The requirements for building from source may have changed,
   especially in minimal container environments (e.g., Alpine Linux).
   See :doc:`development/installing_from_source` for more information.

The legacy ``Makefile`` has been removed in favor of built-in setup.py
commands.

Certain environment variables used at build time have been deprecated
and renamed.

Generated ``.c`` and ``.h`` files are no longer included in the
distribution. Neither are Cython ``.pxd`` files. This is because
linking to internal C optimizations is not supported and likely to
crash if used against a different version of gevent than exactly what
it was compiled for. See :issue:`1568` for more details.

Library Updates
===============

The bundled version of libuv has been updated from 1.24 to 1.34, libev
has been updated from 4.23 to 4.31, and c-ares has been updated from
1.14 to 1.15.

Version 1.16 or newer of dnspython is required to use the dnspython resolver.

Test Updates
============

gevent's test suite has adopted the standard library's notion of "test
resources," allowing users to disable
certain tests based on their resource usage. This is primarily
intended to support downstream packagers. For example, to disable
tests that require Internet access, one could disable the ``network``
resource using ``python -m gevent.tests -u-network`` or
``GEVENTTEST_USE_RESOURCES=-network python -m gevent.tests``. See
:ref:`limiting-test-resource-usage` for more information.

Other Changes
=============

The file objects have been reworked to support more modes and behave
more like the builtin :func:`open` or func:`io.open` functions and
:mod:`io` classes. Previously they essentially only worked with binary
streams. Certain default values have been changed as well.

The deprecated magic proxy object ``gevent.signal`` has been removed.
