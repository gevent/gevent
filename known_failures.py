# This is a list of known failures (=bugs).
# The tests listed there must fail (or testrunner.py will report error) unless they are prefixed with FLAKY
# in which cases the result of them is simply ignored
from __future__ import print_function
import os
import sys
import struct


APPVEYOR = os.getenv('APPVEYOR')
LEAKTEST = os.getenv('GEVENTTEST_LEAKCHECK')
COVERAGE = os.getenv("COVERAGE_PROCESS_START")
PYPY = hasattr(sys, 'pypy_version_info')
PY3 = sys.version_info[0] >= 3
PY26 = sys.version_info[0] == 2 and sys.version_info[1] == 6
PY35 = sys.version_info[0] >= 3 and sys.version_info[1] >= 5
PYGTE279 = (
    sys.version_info[0] == 2
    and sys.version_info[1] >= 7
    and sys.version_info[2] >= 9
)


FAILING_TESTS = [

    # Sometimes fails with AssertionError: ...\nIOError: close() called during concurrent operation on the same file object.\n'
    # Sometimes it contains "\nUnhandled exception in thread started by \nsys.excepthook is missing\nlost sys.stderr\n"
    "FLAKY test__subprocess_interrupted.py",
    # test__issue6 (see comments in test file) is really flaky on both Travis and Appveyor;
    # on Travis we could just run the test again (but that gets old fast), but on appveyor
    # we don't have that option without a new commit---and sometimes we really need a build
    # to succeed in order to get a release wheel
    'FLAKY test__issue6.py',
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
    # other Windows-related issues (need investigating)
    FAILING_TESTS += [
        # fork watchers don't get called in multithreaded programs on windows
        # No idea why.
        'test__core_fork.py',
        'FLAKY test__greenletset.py',
        # This has been seen to fail on Py3 and Py2 due to socket reuse
        # errors, probably timing related again.
        'FLAKY test___example_servers.py',
    ]

    if APPVEYOR:
        FAILING_TESTS += [
            # These both run on port 9000 and can step on each other...seems like the
            # appveyor containers aren't fully port safe? Or it takes longer
            # for the processes to shut down? Or we run them in a different order
            # in the process pool than we do other places?
            'FLAKY test__example_udp_client.py',
            'FLAKY test__example_udp_server.py',
            # This one sometimes times out, often after output "The process with PID XXX could not be
            # terminated. Reason: There is no running instance of the task."
            'FLAKY test__example_portforwarder.py',
        ]

    if not PY35:
        # Py35 added socket.socketpair, all other releases
        # are missing it
        FAILING_TESTS += [
            'test__socketpair.py',
        ]

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
        pass


if LEAKTEST:
    FAILING_TESTS += [
        'FLAKY test__backdoor.py',
        'FLAKY test__socket_errors.py',
    ]

    if os.environ.get("TRAVIS") == "true":
        FAILING_TESTS += [
            # On Travis, this very frequently fails due to timing
            'FLAKY test_signal.py',
        ]


if PYPY:
    FAILING_TESTS += [
        ## Different in PyPy:

        ## Not implemented:

        ## ---

        ## BUGS:

    ]


if PY26:
    FAILING_TESTS += [
        # http://bugs.python.org/issue9446, fixed in 2.7/3
        # https://github.com/python/cpython/commit/a104f91ff4c4560bec7c336afecb094e73a5ab7e
        'FLAKY test_urllib2.py'
    ]

if PY3:
    # No idea / TODO
    FAILING_TESTS += [
        'FLAKY test__socket_dns.py',
    ]

    if os.environ.get("TRAVIS") == "true":
        FAILING_TESTS += [
            # test_cwd_with_relative_executable tends to fail
            # on Travis...it looks like the test processes are stepping
            # on each other and messing up their temp directories
            'FLAKY test_subprocess.py'
        ]

    if LEAKTEST:
        FAILING_TESTS += ['FLAKY test__threadpool.py']
        # refcount problems:
        FAILING_TESTS += [
            'test__timeout.py',
            'FLAKY test__greenletset.py',
            'test__core.py',
            'test__systemerror.py',
            'test__exc_info.py',
            'test__api_timeout.py',
            'test__event.py',
            'test__api.py',
            'test__hub.py',
            'test__queue.py',
            'test__socket_close.py',
            'test__select.py',
            'test__greenlet.py',
            'FLAKY test__socket.py',
        ]

if sys.version_info[:2] == (3, 3) and os.environ.get('TRAVIS') == 'true':
    # Builds after Sept 29th 2015 have all been failing here, but no code that could
    # affect this was changed. Travis is using 3.3.5;
    # locally I cannot reproduce with 3.3.6. Don't mark this FLAKY so that if it starts to
    # work again we get a failure and can remove this.
    # XXX: Builds after Nov 13, 2015 have suddenly started to work again. The
    # Python version reported by Travis is unchanged. Commenting out for now since
    # it's such a bizarre thing I'm expecting it to come back again.
    FAILING_TESTS += [
        #'test__refcount_core.py'
    ]

if sys.version_info[:2] >= (3, 4) and APPVEYOR:
    FAILING_TESTS += [
        # Timing issues on appveyor
        'FLAKY test_selectors.py'
    ]

if COVERAGE:
    # The gevent concurrency plugin tends to slow things
    # down and get us past our default timeout value. These
    # tests in particular are sensitive to it
    FAILING_TESTS += [
        'FLAKY test__issue302monkey.py',
        'FLAKY test__example_portforwarder.py',
        'FLAKY test__threading_vs_settrace.py',
    ]

FAILING_TESTS = [x.strip() for x in set(FAILING_TESTS) if x.strip()]


if __name__ == '__main__':
    print('known_failures:\n', FAILING_TESTS)
