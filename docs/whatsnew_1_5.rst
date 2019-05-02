==========================
 What's new in gevent 1.5
==========================

.. currentmodule:: gevent

.. toctree::
   :maxdepth: 2

   changelog

.. caution::

   This document is currently being written.

Detailed information on what has changed is available in the
:doc:`changelog`. This document summarizes the most important changes
since :doc:`gevent 1.4 <whatsnew_1_4>`.

gevent 1.5 is a small maintenance release featuring bug fixes and a
small number of API improvements.

Platform Support
================

gevent 1.5 drops support for Python 3.4, and drops support for PyPy
< 7.

Packaging Changes
=================

gevent now distributes `manylinux2010
<https://www.python.org/dev/peps/pep-0571/>`_ binary wheels for Linux,
instead of the older ``manylinux1`` standard. This updated
platform tag allows gevent to distribute libuv support by default.
CentOS 6 is the baseline for this tag.

Library Updates
===============

The bundled version of libuv has been updated from 1.24 to 1.27, libev
has been updated from 4.23 to 4.25, and c-ares has been updated from
1.24 to 1.15.

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
