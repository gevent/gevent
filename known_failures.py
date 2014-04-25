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
    # stat watchers are not implemented on pypy
    FAILING_TESTS += ['test__core_stat.py']


if __name__ == '__main__':
    import pprint
    pprint.pprint(FAILING_TESTS)
