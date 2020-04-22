===============
 Running Tests
===============

.. Things to include:

    - Writing tests and the gevent test framework:
      - Avoiding hard test dependencies.
      - Resource usage.
      - test files must be executable
      - Maybe these things belong in a README in the gevent.tests directory?



gevent has an extensive regression test suite, implemented using the
standard :mod:`unittest` module. It uses a :mod:`custom testrunner
<gevent.testing.testrunner>` that provides enhanced test isolation
(important for monkey-patching), runs tests in parallel, and takes
care of other gevent-specific quirks.

.. note::

   The gevent test process runs Python standard library tests with
   gevent's monkey-patches applied to ensure that gevent behaves
   correctly (matches the standard library). The standard library
   :mod:`test` must be available in order to do this.

   This is usually the case automatically, but some distributions
   remove this module. Notably, on Debian, you will probably need
   ``libpythonX.Y-testsuite`` installed to run all the tests.


The test runner has a number of options:

.. command-output:: python -mgevent.tests --help

The simplest way to run all the tests is just to invoke the test
runner, typically from the root of the source checkout::

  (gevent-env) $ python -mgevent.tests
  Running tests in parallel with concurrency 7
  ...
  Ran 3107 tests (skipped=333) in 132 files in 01:52

You can also run an individual gevent test file using the test runner::


  (gevent-env) $ python -m gevent.tests test__util.py
  Running tests in parallel with concurrency 1
  + /.../python -u -mgevent.tests.test__util
  - /.../python -u -mgevent.tests.test__util [Ran 9 tests in 1.1s]

  Longest-running tests:
  1.1 seconds: /.../python -u -mgevent.tests.test__util

  Ran 9 tests in 1 files in 1.1s


Or you can run a monkey-patched standard library test::

  (gevent-env) $ python -m gevent.tests.test___monkey_patching test_socket.py
  Running tests in parallel with concurrency 1
  + /.../python -u -W ignore -m gevent.testing.monkey_test test_socket.py
  Running with patch_all(Event=False): test_socket.py
  Added imports 1
  Skipped testEmptyFileSend (1)
  ...
  Ran 555 tests in 23.042s

  OK (skipped=172)
  - /.../python -u -W ignore -m gevent.testing.monkey_test test_socket.py [took 26.7s]

  Longest-running tests:
  26.7 seconds: /.../python -u -W ignore -m gevent.testing.monkey_test test_socket.py

  Ran 0 tests in 1 files in 00:27

Environment Variables
=====================

Some testrunner options have equivalent environment variables.
Notably, ``--quiet`` is ``GEVENTTEST_QUIET`` and ``-u`` is
``GEVENTTEST_USE_RESOURCES``.

Using tox
=========

Before submitting a pull request, it's a good idea to run the tests
across all supported versions of Python, and to check the code quality
using prospector. This is what is done on Travis CI. Locally it
can be done using tox::

  pip install tox
  tox


Measuring Code Coverage
=======================

This is done on CI so it's not often necessary to do locally.

The testrunner accepts a ``--coverage`` argument to enable code
coverage metrics through the `coverage.py`_ package. That would go
something like this::

  python -m gevent.tests --coverage
  coverage combine
  coverage html -i
  <open htmlcov/index.html>

.. _limiting-test-resource-usage:

Limiting Resource Usage
=======================

gevent supports the standard library test suite's resources. All
resources are enabled by default. Disabling resources disables the
tests that use those resources. For example, to disable tests that
access the external network (the Internet), disable the ``network``
resource. There's an option for this::

  $ python -m gevent.tests -u-network

And an environment variable::

  $ GEVENTTEST_USE_RESOURCES=-network python -m gevent.tests

.. _coverage.py: https://pypi.python.org/pypi/coverage/
.. _coveralls.io: https://coveralls.io/github/gevent/gevent
