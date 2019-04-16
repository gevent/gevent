# This is a list of known failures (=bugs).
# The tests listed there must fail (or testrunner.py will report error) unless they are prefixed with FLAKY
# in which cases the result of them is simply ignored
from __future__ import print_function
import os
import sys
import struct

from gevent.testing.sysinfo import RUNNING_ON_APPVEYOR as APPVEYOR
from gevent.testing.sysinfo import RUNNING_ON_TRAVIS as TRAVIS
from gevent.testing.sysinfo import RUN_LEAKCHECKS as LEAKTEST
from gevent.testing.sysinfo import RUN_COVERAGE as COVERAGE
from gevent.testing.sysinfo import RESOLVER_NOT_SYSTEM

from gevent.testing.sysinfo import PYPY
from gevent.testing.sysinfo import PY3
from gevent.testing.sysinfo import PY35

from gevent.testing.sysinfo import LIBUV

IGNORED_TESTS = []

FAILING_TESTS = [
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

                # Starting in November 2018, on Python 3.7.0, we observe this test crashing.
                # I can't reproduce locally.
                # | C:\Python37-x64\python.exe -u -mgevent.tests.test__greenness
                #   127.0.0.1 - - [09/Nov/2018 16:34:12] code 501, message Unsupported method ('GET')
                #   127.0.0.1 - - [09/Nov/2018 16:34:12] "GET / HTTP/1.1" 501 -
                #   .
                #   ----------------------------------------------------------------------
                #   Ran 1 test in 0.031s

                #   OK
                #   Windows fatal exception: access violation

                #   Current thread 0x000003c8 (most recent call first):
                #     File "c:\projects\gevent\src\gevent\threadpool.py", line 261 in _worker

                #   Thread 0x00000600 (most recent call first):
                #     File "c:\projects\gevent\src\gevent\libuv\watcher.py", line 577 in send
                #     File "c:\projects\gevent\src\gevent\threadpool.py", line 408 in set
                #     File "c:\projects\gevent\src\gevent\threadpool.py", line 290 in _worker

                #   Thread 0x000007d4 (most recent call first):
                #     File "C:\Python37-x64\lib\weakref.py", line 356 in remove

                # ! C:\Python37-x64\python.exe -u -mgevent.tests.test__greenness [code 3221225477] [took 1.3s]
                # We have also seen this for Python 3.6.6 Nov 13 2018:
                # | C:\Python36-x64\python.exe -u -mgevent.tests.test__backdoor
                #   ss.s.s
                #   ----------------------------------------------------------------------
                #   Ran 6 tests in 0.953s

                #   OK (skipped=4)
                #   Windows fatal exception: access violation

                #   Thread 0x00000aec (most recent call first):
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 84 in wait
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 166 in get
                #     File "C:\Python36-x64\lib\site-packages\gevent\threadpool.py", line 270 in _worker

                #   Thread 0x00000548 (most recent call first):

                #   Thread 0x000003d0 (most recent call first):
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 84 in wait
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 166 in get
                #     File "C:\Python36-x64\lib\site-packages\gevent\threadpool.py", line 270 in _worker

                #   Thread 0x00000ad0 (most recent call first):

                #   Thread 0x00000588 (most recent call first):
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 84 in wait
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 166 in get
                #     File "C:\Python36-x64\lib\site-packages\gevent\threadpool.py", line 270 in _worker

                #   Thread 0x00000a54 (most recent call first):

                #   Thread 0x00000768 (most recent call first):
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 84 in wait
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 166 in get
                #     File "C:\Python36-x64\lib\site-packages\gevent\threadpool.py", line 270 in _worker

                #   Current thread 0x00000894 (most recent call first):
                #     File "C:\Python36-x64\lib\site-packages\gevent\threadpool.py", line 261 in _worker

                #   Thread 0x00000634 (most recent call first):
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 84 in wait
                #     File "C:\Python36-x64\lib\site-packages\gevent\_threading.py", line 166 in get
                #     File "C:\Python36-x64\lib\site-packages\gevent\threadpool.py", line 270 in _worker

                #   Thread 0x00000538 (most recent call first):

                #   Thread 0x0000049c (most recent call first):
                #     File "C:\Python36-x64\lib\weakref.py", line 356 in remove

                # ! C:\Python36-x64\python.exe -u -mgevent.tests.test__backdoor [code 3221225477] [Ran 6 tests in 2.1s]

                # Note the common factors:
                # - The test is finished (successfully) and we're apparently exiting the VM,
                #   doing GC
                # - A weakref is being cleaned up

                # weakref.py line 356 remove() is in WeakKeyDictionary. We only use WeakKeyDictionary
                # in gevent._ident.IdentRegistry, which is only used in two places:
                # gevent.hub.hub_ident_registry, which has weak references to Hub objects,
                # and gevent.greenlet.Greenlet.minimal_ident, which uses its parent Hub's
                # IdentRegistry to get its own identifier. So basically they have weak references
                # to Hub and arbitrary Greenlets.

                # Our attempted solution: stop using a module-level IdentRegistry to get
                # Hub idents, and reduce how often we auto-generate one for greenlets.
                # Commenting out the tests, lets see if it works.
                #'FLAKY test__greenness.py',
                #'FLAKY test__backdoor.py',
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
            # AssertionError: ('255.255.255.255', 'http') != gaierror(-2,) # DNS Python
            # AssertionError: ('255.255.255.255', 'http') != gaierror(4, 'ARES_ENOTFOUND: Domain name not found')
            # AssertionError: OverflowError('port must be 0-65535.',) != ('readthedocs.org', '65535')
            # AssertionError: Lists differ:
            #     (10, 1, 6, '', ('2607:f8b0:4004:810::200e', 80, 0L, 0L))
            #     (10, 1, 6, '', ('2607:f8b0:4004:805::200e', 80, 0, 0))
            #
            # Somehow it seems most of these are fixed with PyPy3.6-7 under dnspython,
            # (once we commented out TestHostname)?
            'FLAKY test__socket_dns.py',
        ]

    if LIBUV:
        IGNORED_TESTS += [
            # This hangs for no apparent reason when run by the testrunner,
            # even wher maked standalone
            # when run standalone from the command line, it's fine.
            # Issue in pypy2 6.0?
            'test__monkey_sigchld_2.py',
        ]

    if TRAVIS:
        FAILING_TESTS += [
            # This fails to get the correct results, sometimes. I can't reproduce locally
            'FLAKY test__example_udp_server.py',
            'FLAKY test__example_udp_client.py',
        ]

        IGNORED_TESTS += [
            # PyPy 7.0 and 7.1 on Travis with Ubunto Xenial 16.04
            # can't allocate SSL Context objects, either in Python 2.7
            # or 3.6. There must be some library incompatibility.
            # No point even running them.
            # XXX: Remember to turn this back on.
            'test_ssl.py',
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
            'test__threading_2.py',
        ]

    if PY3 and TRAVIS:
        FAILING_TESTS += [
            ## ---

            ## Unknown; can't reproduce locally on OS X
            'FLAKY test_subprocess.py', # timeouts on one test.
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



if PY3 and APPVEYOR:
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


# A mapping from test file basename to a dictionary of
# options that will be applied on top of the DEFAULT_RUN_OPTIONS.
TEST_FILE_OPTIONS = {

}


# tests that don't do well when run on busy box
RUN_ALONE = [
    'test__threadpool.py',
    'test__examples.py',
]



if APPVEYOR or TRAVIS:
    RUN_ALONE += [
        # Partial workaround for the _testcapi issue on PyPy,
        # but also because signal delivery can sometimes be slow, and this
        # spawn processes of its own
        'test_signal.py',
    ]

    if LEAKTEST and PY3:
        # On a heavily loaded box, these can all take upwards of 200s
        RUN_ALONE += [
            'test__pool.py',
            'test__pywsgi.py',
            'test__queue.py',
        ]

    if PYPY:
        # This often takes much longer on PyPy on CI.
        TEST_FILE_OPTIONS['test__threadpool.py'] = {'timeout': 180}
        TEST_FILE_OPTIONS['test__threading_2.py'] = {'timeout': 180}
        if PY3:
            RUN_ALONE += [
                # Sometimes shows unexpected timeouts
                'test_socket.py',
            ]
        if LIBUV:
            RUN_ALONE += [
                # https://bitbucket.org/pypy/pypy/issues/2769/systemerror-unexpected-internal-exception
                'test__pywsgi.py',
            ]

# tests that can't be run when coverage is enabled
IGNORE_COVERAGE = [
    # Hangs forever
    'test__threading_vs_settrace.py',
    # times out
    'test_socket.py',
    # Doesn't get the exceptions it expects
    'test_selectors.py',
    # XXX ?
    'test__issue302monkey.py',
    "test_subprocess.py",
]

if PYPY:
    IGNORE_COVERAGE += [
        # Tends to timeout
        'test__refcount.py',
        'test__greenletset.py'
    ]

if __name__ == '__main__':
    print('known_failures:\n', FAILING_TESTS)
