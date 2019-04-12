===============================
 Installation and Requirements
===============================

.. _installation:

..
  This file is included in README.rst so it is limited to plain
  ReST markup, not Sphinx.

Supported Platforms
===================

`gevent 1.4`_ runs on Python 2.7 and Python 3. Releases 3.5, 3.6 and
3.7 of Python 3 are supported. (Users of older versions of Python 2
need to install gevent 1.0.x (2.5), 1.1.x (2.6) or 1.2.x (<=2.7.8);
gevent 1.2 can be installed on Python 3.3. and gevent 1.3 can be
installed on Python 3.4.0 - 3.4.2, while gevent 1.4 can be installed
on Python 3.4.3) gevent requires the `greenlet
<https://greenlet.readthedocs.io>`_ library and will install the
`cffi`_ library by default on Windows.

gevent 1.5 also runs on PyPy 5.5 and above, although 6.0 or above is
strongly recommended. On PyPy, there are no external dependencies.

gevent is tested on Windows, macOS, and Linux, and should run on most
other Unix-like operating systems (e.g., FreeBSD, Solaris, etc.)

.. note:: On Windows using the libev backend, gevent is
          limited to a maximum of 1024 open sockets due to
          `limitations in libev`_. This limitation should not exist
          with the default libuv backend.

Installation
============

.. note::

   This section is about installing released versions of gevent
   as distributed on the `Python Package Index`_

.. _Python Package Index: http://pypi.org/project/gevent

gevent and greenlet can both be installed with `pip`_, e.g., ``pip
install gevent``. Installation using `buildout
<http://docs.buildout.org/en/latest/>`_ is also supported.

On Windows, macOS, and Linux, both gevent and greenlet are
distributed as binary `wheels`_.

.. tip::

   You need Pip 8.0 or later, or buildout 2.10.0 to install the binary
   wheels on Windows or macOS. On Linux, you'll need `pip 19
   <https://github.com/pypa/pip/pull/5008>`_ to install the
   manylinux2010 wheels.


Installing From Source
----------------------

If you are unable to use the binary wheels (for platforms where no
pre-built wheels are available or if wheel installation is disabled),
here are some things you need to know.

- You can install gevent from source with ``pip install --no-binary
  gevent gevent``.

- You'll need a working C compiler that can build Python extensions.
  On some platforms, you may need to install Python development
  packages.

- Installing from source requires ``setuptools``. This is installed
  automatically in virtual environments and by buildout. However,
  gevent uses :pep:`496` environment markers in ``setup.py``.
  Consequently, you'll need a version of setuptools newer than 25
  (mid 2016) to install gevent from source; a version that's too old
  will produce a ``ValueError``. Older versions of pipenv may also
  `have issues installing gevent for this reason
  <https://github.com/pypa/pipenv/issues/2113>`_.

- gevent comes with a pyproject.toml file that installs the build
  dependencies, including CFFI (needed for libuv support). pip 18 or
  above is required.


Common Installation Issues
--------------------------

The following are some common installation problems and solutions for
those compiling gevent from source.

- Some Linux distributions are now mounting their temporary
  directories with the ``noexec`` option. This can cause a standard
  ``pip install gevent`` to fail with an error like ``cannot run C
  compiled programs``. One fix is to mount the temporary directory
  without that option. Another may be to use the ``--build`` option to
  ``pip install`` to specify another directory. See `issue #570
  <https://github.com/gevent/gevent/issues/570>`_ and `issue #612
  <https://github.com/gevent/gevent/issues/612>`_ for examples.

- Also check for conflicts with environment variables like ``CFLAGS``. For
  example, see `Library Updates <http://www.gevent.org/whatsnew_1_1.html#library-updates-label>`_.

- Users of a recent SmartOS release may need to customize the
  ``CPPFLAGS`` (the environment variable containing the default
  options for the C preprocessor) if they are using the libev shipped
  with gevent. See `Operating Systems
  <http://www.gevent.org/whatsnew_1_1.html#operating-systems-label>`_
  for more information.

- If you see ``ValueError: ("Expected ',' or end-of-list in", "cffi >=
  1.11.5 ; sys_platform == 'win32' and platform_python_implementation
  == 'CPython'", 'at', " ; sys_platform == 'win32' and
  platform_python_implementation == 'CPython'")``, the version of
  setuptools is too old. Install a more recent version of setuptools.


Extra Dependencies
==================

gevent has no runtime dependencies outside the standard library,
greenlet and (on some platforms) `cffi`_. However, there are a
number of additional libraries that extend gevent's functionality and
will be used if they are available.

The `psutil <https://pypi.org/project/psutil>`_ library is needed to
monitor memory usage.

`zope.event <https://pypi.org/project/zope.event>`_ is highly
recommended for configurable event support; it can be installed with
the ``events`` extra, e.g., ``pip install gevent[events]``.

`dnspython <https://pypi.org/project/dnspython>`_ is required for the
new pure-Python resolver, and on Python 2, so is `idna
<https://pypi.org/project/idna>`_. They can be installed with the
``dnspython`` extra.


Development
===========

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


Running Tests
-------------

There are a few different ways to run the tests. To simply run the
tests on one version of Python during development, begin with the
above instructions to install gevent in a virtual environment and then
run::

  (env) $ python -mgevent.tests

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
.. _`pip`: https://pip.pypa.io/en/stable/installing/
.. _`wheels`: http://pythonwheels.com
.. _`gevent 1.4`: whatsnew_1_4.html

.. _`cffi`: https://cffi.readthedocs.io
.. _`limitations in libev`: http://pod.tst.eu/http://cvs.schmorp.de/libev/ev.pod#WIN32_PLATFORM_LIMITATIONS_AND_WORKA
.. _AppVeyor: https://ci.appveyor.com/project/denik/gevent
