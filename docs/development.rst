=============
 Development
=============

..
    The contributor guide (CONTRIBUTING.rst) references this document.

    Things to include:

    - Avoiding hard test dependencies.
    - Resource usage.
    - Custom commands in ``setup.py``


To install the latest development version::

  pip install git+git://github.com/gevent/gevent.git#egg=gevent

.. note::

   You will not be able to run gevent's test suite using that method.

To hack on gevent (using a virtualenv)::

  $ git clone https://github.com/gevent/gevent.git
  $ cd gevent
  $ virtualenv env
  $ source env/bin/activate
  (env) $ pip install -r dev-requirements.txt

.. note::

   The notes above about installing from source apply here as well.
   The ``dev-requirements.txt`` file takes care of the library
   prerequisites (CFFI, Cython), but having a working C compiler that
   can create Python extensions is up to you.

.. warning::

   This pip command does not work with pip 19.1. Either use pip 19.0
   or below, or use pip 19.1.1 with ``--no-use-pep517``. See `issue
   1412 <https://github.com/gevent/gevent/issues/1412>`_.


Running Tests
-------------

There are a few different ways to run the tests. To simply run the
tests on one version of Python during development, begin with the
above instructions to install gevent in a virtual environment and then
run::

  (env) $ python -mgevent.tests

.. command-output:: python -mgevent.tests --help

Before submitting a pull request, it's a good idea to run the tests
across all supported versions of Python, and to check the code quality
using prospector. This is what is done on Travis CI. Locally it
can be done using tox::

  pip install tox
  tox

The testrunner accepts a ``--coverage`` argument to enable code
coverage metrics through the `coverage.py`_ package. That would go
something like this::

  python -m gevent.tests --coverage
  coverage combine
  coverage html -i
  <open htmlcov/index.html>

Continuous integration
----------------------

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
