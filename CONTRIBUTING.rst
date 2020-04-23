========================
 Contributing to gevent
========================

Please see `contribution-guide.org
<http://www.contribution-guide.org/>`_ for general details on what we
need from contributors.

If you're filing a bug that needs a code example, please be sure it's
a `Short, Self Contained, Correct, Example <http://sscce.org>`_

Thanks!


gevent-specific details
=======================

For information on building gevent, and adding and updating test
cases, see `the development documentation
<http://www.gevent.org/contents.html#contents-developing>`_.

There are a number of systems in place to help ensure gevent is of the
highest possible quality:

- A test suite is run for every push and pull request submitted. Travis
  CI is used to test on Linux and macOS, and `AppVeyor`_ runs the builds on
  Windows. Pull requests with tests that don't pass will be
  automatically failed.

  .. image:: https://travis-ci.org/gevent/gevent.svg?branch=master
     :target: https://travis-ci.org/gevent/gevent

  .. image:: https://ci.appveyor.com/api/projects/status/q4kl21ng2yo2ixur?svg=true
     :target: https://ci.appveyor.com/project/denik/gevent

- Builds on Travis CI automatically submit updates to `coveralls.io`_ to
  monitor test coverage. Pull requests that don't feature adequate test
  coverage will be automatically failed.

  .. image:: https://coveralls.io/repos/gevent/gevent/badge.svg?branch=master&service=github
     :target: https://coveralls.io/github/gevent/gevent?branch=master

- Travis CI builds also run `pylint
  <https://pylint.readthedocs.io/en/latest/>`_ to enforce code quality
  conventions (PEP8 compliance and the like).


.. _coveralls.io: https://coveralls.io/github/gevent/gevent
.. _AppVeyor: https://ci.appveyor.com/project/denik/gevent

Pull requests that don't pass those checks will be automatically
failed. But don't worry, it's all about context. Most of the time
failing checks are easy to fix, and occasionally a PR will be accepted
even with failing checks to be fixed by the maintainers.
