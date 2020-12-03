========================
 Continuous integration
========================

A test suite is run for every push and pull request submitted. Github Actions
CI is used to test on Linux and macOS, and `AppVeyor`_ runs the builds on
Windows.

.. image:: https://github.com/gevent/gevent/workflows/gevent%20testing/badge.svg
   :target: https://github.com/gevent/gevent/actions

.. image:: https://ci.appveyor.com/api/projects/status/q4kl21ng2yo2ixur?svg=true
   :target: https://ci.appveyor.com/project/denik/gevent


Builds on Github Actions CI automatically submit updates to `coveralls.io`_ to
monitor test coverage.

.. image:: https://coveralls.io/repos/gevent/gevent/badge.svg?branch=master&service=github
   :target: https://coveralls.io/github/gevent/gevent?branch=master


.. _coverage.py: https://pypi.python.org/pypi/coverage/
.. _coveralls.io: https://coveralls.io/github/gevent/gevent
.. _AppVeyor: https://ci.appveyor.com/project/denik/gevent
