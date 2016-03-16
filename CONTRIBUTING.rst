Basics
======

Please see `contribution-guide.org <http://www.contribution-guide.org/>`_ for
general details on what we expect from contributors. Thanks!


gevent-specific details
=======================

There are a number of systems in place to help ensure gevent is of the
highest possible quality:

- Builds on Travis CI automatically submit updates to `coveralls.io`_ to
  monitor test coverage. Pull requests that don't feature adequate test
  coverage will be automatically failed.

.. image:: https://coveralls.io/repos/gevent/gevent/badge.svg?branch=master&service=github
   :target: https://coveralls.io/github/gevent/gevent?branch=master

- Likewise, builds on Travis CI will automatically submit updates to
  `landscape.io`_ to monitor code health (adherence to PEP8, absence of
  common code smells, etc). Pull requests that decrease code health will
  be automatically failed.

.. image:: https://landscape.io/github/gevent/gevent/master/landscape.svg?style=flat
   :target: https://landscape.io/github/gevent/gevent/master
   :alt: Code Health

- A test suite is run for every push and pull request submitted. Travis
  CI is used to test on Linux, and `AppVeyor`_ runs the builds on
  Windows. Pull requests with tests that don't pass will be
  automatically failed.

.. image:: https://travis-ci.org/gevent/gevent.svg?branch=master
   :target: https://travis-ci.org/gevent/gevent

.. image:: https://ci.appveyor.com/api/projects/status/q4kl21ng2yo2ixur?svg=true
   :target: https://ci.appveyor.com/project/denik/gevent

.. _landscape.io: https://landscape.io/github/gevent/gevent
.. _coveralls.io: https://coveralls.io/github/gevent/gevent
.. _AppVeyor: https://ci.appveyor.com/project/denik/gevent

Pull requests that don't pass those checks will be automatically
failed. But don't worry, it's all about context. Most of the time
failing checks are easy to fix, and occasionally a PR will be accepted
even with failing checks to be fixed by the maintainers.
