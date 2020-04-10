==========================
 What's new in gevent 1.4
==========================

.. currentmodule:: gevent

.. toctree::
   :maxdepth: 2

   changelog_1_4

Detailed information on what has changed is available in the
:doc:`changelog`. This document summarizes the most important changes
since :doc:`gevent 1.3 <whatsnew_1_3>`.

gevent 1.4 is a small maintenance release featuring bug fixes and a
small number of API improvements.

Platform Support
================

gevent 1.4 supports the platforms that gevent 1.3 supported, with the
exception that for users of Python 3.4, Python 3.4.3 is the minimum
supported version.

Test Changes
============

gevent's own test suite is now packaged as part of the gevent install,
and the ``greentest/testrunner.py`` script is now gone from a source
distribution or checkout. Instead, tests can be run with ``python -m
gevent.tests``. Many tests can be run given an installed version of
gevent, although the test dependencies, including cffi, must be
installed for all of them to run.
