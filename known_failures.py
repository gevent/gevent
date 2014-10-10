# This is a list of known failures (=bugs).
# The tests listed there must fail (or testrunner.py will report error) unless they are prefixed with FLAKY
# in which cases the result of them is simply ignored
import os
import sys


CPYTHON_DBG = hasattr(sys, 'gettotalrefcount')
PYPY = hasattr(sys, 'pypy_version_info')
PY3 = sys.version_info[0] >= 3


FAILING_TESTS = [
    # needs investigating
    'FLAKY test__issue6.py',

    # bunch of SSLError: [Errno 1] _ssl.c:504: error:14090086:SSL routines:SSL3_GET_SERVER_CERTIFICATE:certificate verify failed
    # seems to be Python/OpenSSL problem, not gevent's
    'monkey_test --Event test_ssl.py',
    'monkey_test test_ssl.py',

    # Sometimes fails with AssertionError: ...\nIOError: close() called during concurrent operation on the same file object.\n'
    # Sometimes it contains "\nUnhandled exception in thread started by \nsys.excepthook is missing\nlost sys.stderr\n"
    "FLAKY test__subprocess_interrupted.py",
]


if os.environ.get('GEVENT_RESOLVER') == 'ares' or CPYTHON_DBG:
    # XXX fix this
    FAILING_TESTS += [
        'FLAKY test__socket_dns.py',
        'FLAKY test__socket_dns6.py',
    ]


if sys.platform == 'win32':
    # currently gevent.core.stat watcher does not implement 'prev' and 'attr' attributes on Windows
    FAILING_TESTS += ['test__core_stat.py']

    # other Windows-related issues (need investigating)
    FAILING_TESTS += [
        'monkey_test test_threading.py',
        'monkey_test --Event test_threading.py',
        'monkey_test test_subprocess.py',
        'monkey_test --Event test_subprocess.py'
    ]


if CPYTHON_DBG:
    FAILING_TESTS += ['FLAKY test__backdoor.py']
    FAILING_TESTS += ['FLAKY test__os.py']


if PYPY:
    FAILING_TESTS += [
        # Not implemented:

        # stat watchers are not implemented on pypy
        'test__core_stat.py',

        # ares not supported on PyPy yet
        'test__ares_host_result.py',

        # ---

        # BUGS:

        # https://bugs.pypy.org/issue1743
        'test__real_greenlet.py',
        'test__exc_info.py',

        # in CPython we compile _semaphore.py with Cython to make its operation atomic
        # how to do atomic operations on PyPy?
        'test__threading_vs_settrace.py',


        # check_sendall_interrupted and testInterruptedTimeout fail due to
        # https://bitbucket.org/cffi/cffi/issue/152/handling-errors-from-signal-handlers-in
        'test_socket.py',

        # No idea!
        'test_threading_2.py',
        'test_threading.py',
        'test__pywsgi.py',
        'test__backdoor.py',
        'test__refcount.py',
        'test__server.py',
        'test_subprocess.py',  # test_executable_without_cwd
        'FLAKY test___example_servers.py'
    ]


if PY3:
    # No idea / TODO
    FAILING_TESTS += '''
test__example_udp_server.py
test__examples.py
test__pool.py
FLAKY test___example_servers.py
test__example_udp_client.py
test__os.py
test__backdoor.py
test_threading_2.py
test__refcount.py
test__socket.py
test__subprocess.py
test__all__.py
test__fileobject.py
test__pywsgi.py
test__socket_ex.py
test__example_echoserver.py
test__subprocess_poll.py
test__ssl.py
test__makefile_ref.py
test__socketpair.py
test__server_pywsgi.py
test__core_stat.py
test__server.py
test__example_portforwarder.py
test__execmodules.py
FLAKY test__greenio.py
'''.strip().split('\n')

    if os.environ.get('GEVENT_RESOLVER') == 'ares':
        FAILING_TESTS += [
            'test__greenness.py']

    if CPYTHON_DBG:
        FAILING_TESTS += ['FLAKY test__threadpool.py']
        # refcount problems:
        FAILING_TESTS += '''
            test__timeout.py
            test__greenletset.py
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
'''.strip().split()


if __name__ == '__main__':
    import pprint
    pprint.pprint(FAILING_TESTS)
