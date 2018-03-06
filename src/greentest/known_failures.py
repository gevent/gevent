# This is a list of known failures (=bugs).
# The tests listed there must fail (or testrunner.py will report error) unless they are prefixed with FLAKY
# in which cases the result of them is simply ignored
from __future__ import print_function
import os
import sys
import struct

from greentest.sysinfo import RUNNING_ON_APPVEYOR as APPVEYOR
from greentest.sysinfo import RUNNING_ON_TRAVIS as TRAVIS
from greentest.sysinfo import RUN_LEAKCHECKS as LEAKTEST
from greentest.sysinfo import RUN_COVERAGE as COVERAGE
from greentest.sysinfo import RESOLVER_NOT_SYSTEM

from greentest.sysinfo import PYPY
from greentest.sysinfo import PY3
from greentest.sysinfo import PY35

from greentest.sysinfo import LIBUV

IGNORED_TESTS = []

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
    IGNORED_TESTS = [
        # fork watchers don't get called on windows
        # because fork is not a concept windows has.
        # See this file for a detailed explanation.
        'test__core_fork.py',
    ]
    # other Windows-related issues (need investigating)
    FAILING_TESTS += [
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
            # these are most commonly (only?) observed on Py27/64-bit.
            # They also appear on 64-bit 3.6 with libuv
            'FLAKY test__fileobject.py',
        ]

        if PYPY and LIBUV:
            IGNORED_TESTS += [
                # This one seems to just stop right after
                # patching is done. It passes on a local win 10 vm, and the main
                # test_threading_2.py does as well.
                # Based on the printouts we added, it appears to not even
                # finish importing:
                # https://ci.appveyor.com/project/denik/gevent/build/1.0.1277/job/tpvhesij5gldjxqw#L1190
                # Ignored because it takes two minutes to time out.
                'test_threading.py',
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
        # are missing it. No reason to even test it.
        IGNORED_TESTS += [
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

        ## UNKNOWN:
        #   AssertionError: '>>> ' != ''
        # test__backdoor.py:52
        'FLAKY test__backdoor.py',
    ]

    if RESOLVER_NOT_SYSTEM:

        FAILING_TESTS += [
            # A few errors and differences:
            # AssertionError: ('255.255.255.255', 'http') != gaierror(4, 'ARES_ENOTFOUND: Domain name not found')
            # AssertionError: OverflowError('port must be 0-65535.',) != ('readthedocs.org', '65535')
            # AssertionError: Lists differ:
            #     (10, 1, 6, '', ('2607:f8b0:4004:810::200e', 80, 0L, 0L))
            #     (10, 1, 6, '', ('2607:f8b0:4004:805::200e', 80, 0, 0))
            'test__socket_dns.py',
        ]

    if TRAVIS:
        FAILING_TESTS += [
            # This fails to get the correct results, sometimes. I can't reproduce locally
            'FLAKY test__example_udp_server.py',
            'FLAKY test__example_udp_client.py',
        ]

        if LIBUV:
            IGNORED_TESTS += [
                # XXX: Re-enable this when we can investigate more.
                # This has started crashing with a SystemError.
                # I cannot reproduce with the same version on macOS
                # and I cannot reproduce with the same version in a Linux vm.
                # Commenting out individual tests just moves the crash around.
                # https://bitbucket.org/pypy/pypy/issues/2769/systemerror-unexpected-internal-exception
                'test__pywsgi.py',
            ]

        IGNORED_TESTS += [
            # XXX Re-enable these when we have more time to investigate.
            # This test, which normally takes ~60s, sometimes
            # hangs forever after running several tests. I cannot reproduce,
            # it seems highly load dependent. Observed with both libev and libuv.
            'test__threadpool.py',
            # This test, which normally takes 4-5s, sometimes
            # hangs forever after running two tests. I cannot reproduce,
            # it seems highly load dependent. Observed with both libev and libuv.
            'test_threading_2.py',
        ]

    if PY3 and TRAVIS:
        FAILING_TESTS += [
            ## ---

            ## Unknown; can't reproduce locally on OS X
            'FLAKY test_subprocess.py', # timeouts on one test.

            'FLAKY test_ssl.py',
        ]


if LIBUV:
    if sys.platform.startswith("darwin"):
        FAILING_TESTS += [
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
