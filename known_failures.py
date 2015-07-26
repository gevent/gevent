# This is a list of known failures (=bugs).
# The tests listed there must fail (or testrunner.py will report error) unless they are prefixed with FLAKY
# in which cases the result of them is simply ignored
from __future__ import print_function
import os
import sys
import struct


LEAKTEST = os.getenv('GEVENTTEST_LEAKCHECK')
PYPY = hasattr(sys, 'pypy_version_info')
PY3 = sys.version_info[0] >= 3
PYGTE279 = (
    sys.version_info[0] == 2
    and sys.version_info[1] >= 7
    and sys.version_info[2] >= 9
)


FAILING_TESTS = [

    # Sometimes fails with AssertionError: ...\nIOError: close() called during concurrent operation on the same file object.\n'
    # Sometimes it contains "\nUnhandled exception in thread started by \nsys.excepthook is missing\nlost sys.stderr\n"
    "FLAKY test__subprocess_interrupted.py",
]


if os.environ.get('GEVENT_RESOLVER') == 'ares' or LEAKTEST:
    # XXX fix this
    FAILING_TESTS += [
        'FLAKY test__socket_dns.py',
        'FLAKY test__socket_dns6.py',
    ]
else:
    FAILING_TESTS += [
        # A number of the host names hardcoded have multiple, load
        # balanced DNS entries. Therefore, multiple sequential calls
        # of the resolution function, whether gevent or stdlib, can
        # return non-equal results, possibly dependent on the host
        # dns configuration
        'FLAKY test__socket_dns6.py',
    ]

if sys.platform == 'win32':
    # currently gevent.core.stat watcher does not implement 'prev' and 'attr' attributes on Windows
    FAILING_TESTS += ['test__core_stat.py']

    # other Windows-related issues (need investigating)
    FAILING_TESTS += '''
test__all__.py
test__core_fork.py
test__issues461_471.py
test__execmodules.py
test__socketpair.py
test__makefile_ref.py
FLAKY test__greenletset.py
'''.split('\n')

    if struct.calcsize('P') * 8 == 64:
        # could be a problem of appveyor - not sure
        #  ======================================================================
        #   ERROR: test_af (__main__.TestIPv6Environment)
        #  ----------------------------------------------------------------------
        #   File "C:\Python27-x64\lib\ftplib.py", line 135, in connect
        #     self.sock = socket.create_connection((self.host, self.port), self.timeout)
        #   File "c:\projects\gevent\gevent\socket.py", line 73, in create_connection
        #     raise err
        #   error: [Errno 10049] [Error 10049] The requested address is not valid in its context.
        FAILING_TESTS.append('test_ftplib.py')

    if PY3:
        # XXX need investigating
        FAILING_TESTS += '''
            test__example_portforwarder.py
            test__socket_ex.py
            test__examples.py
            test_hub_join_timeout.py
            test_subprocess.py
            test__issue600.py
            test__subprocess.py
            test_threading_2.py
            test__api_timeout.py
            test__subprocess_poll.py
            test__example_udp_client.py
        '''.split('\n')


if LEAKTEST:
    FAILING_TESTS += [
        'FLAKY test__backdoor.py',
        'FLAKY test__socket_errors.py'
    ]


if PYPY:
    FAILING_TESTS += [
        ## Different in PyPy:

        ## Not implemented:

        ## ---

        ## BUGS:

    ]

    import cffi
    if cffi.__version_info__ < (1, 2, 0):
        FAILING_TESTS += [

            # check_sendall_interrupted and testInterruptedTimeout fail due to
            # https://bitbucket.org/cffi/cffi/issue/152/handling-errors-from-signal-handlers-in
            # See also patched_tests_setup and 'test_signal.InterProcessSignalTests.test_main'
            'test_socket.py',
        ]


if PY3:
    # No idea / TODO
    FAILING_TESTS += '''
FLAKY test__socket_dns.py
'''.split('\n')

    if LEAKTEST:
        FAILING_TESTS += ['FLAKY test__threadpool.py']
        # refcount problems:
        FAILING_TESTS += '''
            test__timeout.py
            FLAKY test__greenletset.py
            test__core.py
            test__systemerror.py
            test__exc_info.py
            test__api_timeout.py
            test__event.py
            test__api.py
            test__hub.py
            test__queue.py
            test__socket_close.py
            test__select.py
            test__greenlet.py
            FLAKY test__socket.py
'''.split('\n')

FAILING_TESTS = [x.strip() for x in FAILING_TESTS if x.strip()]


if __name__ == '__main__':
    print ('known_failures:\n', FAILING_TESTS)
