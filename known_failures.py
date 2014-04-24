# This is a list of known failures (=bugs).
import os
import sys


CPYTHON_DBG = hasattr(sys, 'gettotalrefcount')
PYPY = hasattr(sys, 'pypy_version_info')


FAILING_TESTS = [
    # needs investigating
    'test__issue6.py',

    # bunch of SSLError: [Errno 1] _ssl.c:504: error:14090086:SSL routines:SSL3_GET_SERVER_CERTIFICATE:certificate verify failed
    # seems to be Python/OpenSSL problem, not gevent's
    'monkey_test --Event test_ssl.py',
    'monkey_test test_ssl.py',
]


if os.environ.get('GEVENT_RESOLVER') == 'ares':
    # XXX fix this
    FAILING_TESTS += [
        'test__socket_dns.py',
        'test__socket_dns6.py',
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
    FAILING_TESTS += ['test__backdoor.py']


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
        'test__example_portforwarder.py',
        'test__pywsgi.py',
        'test__backdoor.py',
        'test__refcount.py',
        'test__server.py',
        'test_subprocess.py',  # test_executable_without_cwd
    ]


if __name__ == '__main__':
    import pprint
    pprint.pprint(FAILING_TESTS)
