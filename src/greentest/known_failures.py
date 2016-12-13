# This is a list of known failures (=bugs).
# The tests listed there must fail (or testrunner.py will report error) unless they are prefixed with FLAKY
# in which cases the result of them is simply ignored
from __future__ import print_function
import os
import sys
import struct


APPVEYOR = os.getenv('APPVEYOR')
TRAVIS = os.getenv('TRAVIS')
LEAKTEST = os.getenv('GEVENTTEST_LEAKCHECK')
COVERAGE = os.getenv("COVERAGE_PROCESS_START")
PYPY = hasattr(sys, 'pypy_version_info')
PY3 = sys.version_info[0] >= 3
PY26 = sys.version_info[0] == 2 and sys.version_info[1] == 6
PY27 = sys.version_info[0] == 2 and sys.version_info[1] == 7
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
            # This one sometimes randomly closes connections, but no indication
            # of a server crash, only a client side close.
            'FLAKY test__server_pywsgi.py',
            # We only use FileObjectThread on Win32. Sometimes the
            # visibility of the 'close' operation, which happens in a
            # background thread, doesn't make it to the foreground
            # thread in a timely fashion, leading to 'os.close(4) must
            # not succeed' in test_del_close. We have the same thing
            # with flushing and closing in test_newlines. Both of
            # these are most commonly (only?) observed on Py27/64-bit
            'FLAKY test__fileobject.py',
        ]

        FAILING_TESTS += [
            # This sometimes fails with a timeout, meaning
            # one of the tests hangs (test_fullduplex, maybe?).
            # But only sometimes, and only seen on Py2.7, beginning
            # ~2016-02-24.
            # Beginning Apr 2016 sometimes also seen with Py 3.5
            'FLAKY test__socket.py',
        ]

        if PY3:
            FAILING_TESTS += [
                # test_set_and_clear in Py3 relies on 5 threads all starting and
                # coming to an Event wait point while a sixth thread sleeps for a half
                # second. The sixth thread then does something and checks that
                # the 5 threads were all at the wait point. But the timing is sometimes
                # too tight for appveyor. This happens even if Event isn't
                # monkey-patched
                'FLAKY test_threading.py',
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
        # XXX: On Jan 3 2016 this suddenly started passing on Py27/64; no idea why, the python version
        # was 2.7.11 before and after.
        FAILING_TESTS.append('FLAKY test_ftplib.py')

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

    if PY3 and TRAVIS:
        FAILING_TESTS += [
            ## ---

            ## Unknown; can't reproduce locally on OS X
            'FLAKY test_subprocess.py', # timeouts on one test.
        ]


if PY26:
    FAILING_TESTS += [
        # http://bugs.python.org/issue9446, fixed in 2.7/3
        # https://github.com/python/cpython/commit/a104f91ff4c4560bec7c336afecb094e73a5ab7e
        'FLAKY test_urllib2.py',
    ]

    if TRAVIS:
        # Started seeing this with a fresh build of 2.6.9
        # on 2016-02-11. Can't reproduce locally.
        # test__all__.test_ssl: items 'name', 'value' from
        # stdlib module not found in gevent module.
        # Which makes no sense. 2.6 isn't supported by python.org
        # anymore, though, and we're starting to get warnings about
        # pip.
        FAILING_TESTS += [
            'test__all__.py',
        ]

if PY3:
    # No idea / TODO
    FAILING_TESTS += [
        'FLAKY test__socket_dns.py',
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
