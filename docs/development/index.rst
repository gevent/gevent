=============
 Development
=============

This document provides information about developing gevent itself,
including information about running tests.

More information is in the ``CONTRIBUTING.rst`` document in the root
of the gevent repository.

..
    The contributor guide (CONTRIBUTING.rst) references this document.

    Things to include:

    - Custom commands in ``setup.py``
    - Writing tests and the gevent test framework:
      - Avoiding hard test dependencies.
      - Resource usage.
      - test files must be executable
      - Maybe these things belong in a README in the gevent.tests directory?


Getting Started
===============

Developing gevent requires being able to install gevent from source.
See :doc:`installing_from_source` for general information about that.

It is recommended to install the development copy of gevent in a
`virtual environment <https://docs.python.org/3/tutorial/venv.html>`_;
you can use the :mod:`venv` module distributed with Python 3, or
`virtualenv <https://pypi.org/project/virtualenv/>`_, possibly with
`virtualenvwrapper <https://pypi.org/project/virtualenvwrapper/>`_.

You may want a different virtual environment for each Python
implementation and version that you'll be working with. gevent
includes a `tox <http://tox.readthedocs.org/>`_ configuration for
automating the process of testing across multiple Python versions, but
that can be slow.

The rest of this document will assume working in an isolated virtual
environment, but usually won't show that in the prompt. An example of
creating a virtual environment is shown here::

  $ python3 -m venv gevent-env
  $ cd gevent-env
  $ . bin/activate
  (gevent-env) $


To work on gevent, we'll need to get the source, install gevent's
dependencies, including test dependencies, and install gevent as an
`editable install
<https://pip.pypa.io/en/stable/reference/pip_install/#editable-installs>`_
using pip's `-e option` (also known as `development mode
<https://setuptools.readthedocs.io/en/latest/setuptools.html#development-mode>`_,
this is mostly the same as running ``python setup.py develop``).

Getting the source means cloning the git repository::

  (gevent-env) $ git clone https://github.com/gevent/gevent.git
  (gevent-env) $ cd gevent

Installing gevent's dependencies, test dependencies, and gevent itself
can be done in one line by installing the ``dev-requirements.txt`` file::

  (gevent-env) $ pip install -r dev-requirements.txt

.. warning::

   This pip command does not work with pip 19.1. Either use pip 19.0
   or below, or use pip 19.1.1 with ``--no-use-pep517``. See `issue
   1412 <https://github.com/gevent/gevent/issues/1412>`_.


Running Tests
=============

gevent has an extensive regression test suite, implemented using the
standard :mod:`unittest` module. It uses a :mod:`custom testrunner
<gevent.testing.testrunner>` that provides enhanced test isolation
(important for monkey-patching), runs tests in parallel, and takes
care of other gevent-specific quirks.

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
---------------------

Some testrunner options have equivalent environment variables.
Notably, ``--quiet`` is ``GEVENTTEST_QUIET`` and ``-u`` is
``GEVENTTEST_USE_RESOURCES``.

Using tox
---------

Before submitting a pull request, it's a good idea to run the tests
across all supported versions of Python, and to check the code quality
using prospector. This is what is done on Travis CI. Locally it
can be done using tox::

  pip install tox
  tox


Measuring Code Coverage
-----------------------

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
-----------------------

gevent supports the standard library test suite's resources. All
resources are enabled by default. Disabling resources disables the
tests that use those resources. For example, to disable tests that
access the external network (the Internet), disable the ``network``
resource. There's an option for this::

  $ python -m gevent.tests -u-network

And an environment variable::

  $ GEVENTTEST_USE_RESOURCES=-network python -m gevent.tests

Continuous integration
======================

A test suite is run for every push and pull request submitted. Travis
CI is used to test on Linux, and `AppVeyor`_ runs the builds on
Windows.

.. image:: https://travis-ci.org/gevent/gevent.svg?branch=master
   :target: https://travis-ci.org/gevent/gevent

.. image:: https://ci.appveyor.com/api/projects/status/q4kl21ng2yo2ixur?svg=true
   :target: https://ci.appveyor.com/project/denik/gevent


Builds on Travis CI automatically submit updates to `coveralls.io`_ to
monitor test coverage.

.. image:: https://coveralls.io/repos/gevent/gevent/badge.svg?branch=master&service=github
   :target: https://coveralls.io/github/gevent/gevent?branch=master

.. note:: On Debian, you will probably need ``libpythonX.Y-testsuite``
          installed to run all the tests.


.. _coverage.py: https://pypi.python.org/pypi/coverage/
.. _coveralls.io: https://coveralls.io/github/gevent/gevent
.. _AppVeyor: https://ci.appveyor.com/project/denik/gevent

Releasing gevent
================

.. note:: This is a semi-organized collection of notes for gevent
          maintainers.

gevent is released using `zest.releaser
<https://pypi.org/project/zest.releaser/>`_. The general flow is
something like this:

1. Push all relevant changes to master.
2. From the gevent working copy, run ``prerelease``. Fix any issues it
   brings up. Let it bump the version number (or enter the correct
   one) and commit.
3. Run ``release``. Let it create the tag and commit it; let it create
   an sdist, but **do not** let it upload it.
4. Push the tag and master to github.
5. Let appveyor build the tag. Download all the built wheels from that
   release. The easiest way to do that is with Ned Batchelder's
   `appveyor-download.py script
   <https://bitbucket.org/ned/coveragepy/src/tip/ci/download_appveyor.py>`_.
6. Meanwhile, spin up docker and from the root of the gevent checkout
   run ``scripts/releases/make-manylinux``. This creates wheels in
   ``wheelhouse/``.
7. If on a mac, ``cd scripts/releases && ./geventreleases.sh``. This
   creates wheels in ``/tmp/gevent/``.
8. Upload the Appveyor, manylinux, and mac wheels to pypi using
   ``twine``. Also be sure to upload the sdist!
9. Run ``postrelease``, let it bump the version and push the changes
   to github.
