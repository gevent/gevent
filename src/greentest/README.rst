=================
 Versioned Tests
=================

The test directories that begin with a number (e.g., 2.7 and 3.5) are
copies of the standard library tests for that specific version of
Python. Each directory has a ``version`` file that identifies the
specific point release the tests come from. The tests are only
expected to pass if the version of python running the tests exactly
matches the version in that file. If this is not the case, the test
runner will print a warning.

.. caution:: For ease of updating the standard library tests, gevent
             tries very hard not to modify the tests if at all
             possible. Prefer to use the ``patched_tests_setup.py`` or
             ``known_failures.py`` file if necessary.

             One exception to this is ``test_threading.py``, where we
             find it necessary to change 'from test import lock_tests'
             to our own 'from gevent.tests import lock_tests'.
