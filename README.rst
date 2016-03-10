========
 gevent
========

gevent_ is a coroutine-based Python networking library.

Features include:

* Fast event loop based on libev_.
* Lightweight execution units based on greenlet_.
* Familiar API that re-uses concepts from the Python standard library.
* Cooperative sockets with SSL support.
* DNS queries performed through c-ares_ or a threadpool.
* Ability to use standard library and 3rd party modules written for standard blocking sockets

gevent_ is `inspired by eventlet`_ but features more consistent API,
simpler implementation and better performance. Read why others `use
gevent`_ and check out the list of the `open source projects based on
gevent`_.

gevent is licensed under the MIT license.

See `what's new`_ in the latest major release.

Check out the detailed changelog_ for this version.

Get gevent
==========

Gevent runs on Python >= 2.6, Python >= 3.3, or PyPy >= 4.0.1
(but not PyPy3) (*Note*: PyPy is not supported in Windows). On all
platforms, installing setuptools is recommended (this is done
automatically if working in a virtual environment).

You can use pip to install gevent::

    pip install gevent

*Note:* You need Pip 8.0 or later to install the binary wheels for 1.1.

**Important:** Version 1.1 will be the last gevent series to support
Python 2.6. Future major releases will only support Python 2.7 and above.

Download the latest release from `Python Package Index`_ or clone `the repository`_.

Read the documentation online at http://www.gevent.org. Additional
installation information can be found `here <http://www.gevent.org/intro.html#installation-and-requirements>`_.

Post feedback and issues on the `bug tracker`_, `mailing list`_, blog_
and `twitter (@gevent)`_.


Development
===========

To install the latest development version::

  pip install setuptools 'cython>=0.23.4' git+git://github.com/gevent/gevent.git#egg=gevent

To hack on gevent (using a virtualenv)::

  $ git clone https://github.com/gevent/gevent.git
  $ cd gevent
  $ virtualenv env
  $ source env/bin/activate
  (env) $ pip install -r dev-requirements.txt

.. note::

   You must have Cython, a C compiler, and the Python
   development headers installed to build a checkout. Installing CFFI
   on CPython (it's standard on PyPy) allows building the CFFI backend
   for testing, and tox is the command used to test multiple versions
   of Python.

Running Tests
-------------

There are a few different ways to run the tests. To simply run the
tests on one version of Python during development, try this::

  python setup.py develop
  cd greentest
  PYTHONPATH=.. python testrunner.py --config ../known_failures.py

Before submitting a pull request, it's a good idea to run the tests
across all supported versions of Python, and to check the code quality
using pep8 and pyflakes. This is what is done on Travis CI. Locally it
can be done using tox::

  pip install tox
  tox


The testrunner accepts a ``--coverage`` argument to enable code
coverage metrics through the `coverage.py`_ package. That would go
something like this::

  cd greentest
  PYTHONPATH=.. python testrunner.py --config ../known_failures.py --coverage
  coverage combine
  coverage html -i
  <open htmlcov/index.html>

Builds on Travis CI automatically submit updates to `coveralls.io`_.

.. image:: https://coveralls.io/repos/gevent/gevent/badge.svg?branch=maint/1.1.x&service=github
   :target: https://coveralls.io/github/gevent/gevent?branch=maint/1.1.x

Continuous integration
----------------------

A test suite is run for every push and pull request submitted. Travis
CI is used to test on Linux, and `AppVeyor`_ runs the builds on Windows.

.. image:: https://travis-ci.org/gevent/gevent.svg?branch=maint%2F1.1.x
   :target: https://travis-ci.org/gevent/gevent

.. image:: https://ci.appveyor.com/api/projects/status/q4kl21ng2yo2ixur/branch/maint%2F1.1.x?svg=true
   :target: https://ci.appveyor.com/project/denik/gevent

.. _gevent: http://www.gevent.org
.. _greenlet: http://pypi.python.org/pypi/greenlet
.. _libev: http://libev.schmorp.de/
.. _c-ares: http://c-ares.haxx.se/
.. _inspired by eventlet: http://blog.gevent.org/2010/02/27/why-gevent/
.. _use gevent: http://groups.google.com/group/gevent/browse_thread/thread/4de9703e5dca8271
.. _open source projects based on gevent: https://github.com/gevent/gevent/wiki/Projects
.. _Python Package Index: http://pypi.python.org/pypi/gevent
.. _the repository: https://github.com/gevent/gevent
.. _bug tracker: https://github.com/gevent/gevent/wiki/Projects
.. _mailing list: http://groups.google.com/group/gevent
.. _blog: http://blog.gevent.org
.. _twitter (@gevent): http://twitter.com/gevent
.. _coverage.py: https://pypi.python.org/pypi/coverage/
.. _coveralls.io: https://coveralls.io/github/gevent/gevent
.. _AppVeyor: https://ci.appveyor.com/project/denik/gevent
.. _what's new: http://www.gevent.org/whatsnew_1_1.html
.. _changelog: http://www.gevent.org/changelog.html
