# This is a list of known failures (=bugs).
# The tests listed there must fail (or testrunner.py will report error) unless they are prefixed with FLAKY
# in which cases the result of them is simply ignored
import os
import sys


CPYTHON_DBG = hasattr(sys, 'gettotalrefcount')
PYPY = hasattr(sys, 'pypy_version_info')


FAILING_TESTS = [
    # needs investigating
    'FLAKY test__issue6.py',

    # Sometimes fails with AssertionError: ...\nIOError: close() called during concurrent operation on the same file object.\n'
    # Sometimes it contains "\nUnhandled exception in thread started by \nsys.excepthook is missing\nlost sys.stderr\n"
    "FLAKY test__subprocess_interrupted.py",
]

if sys.version_info[:2] <= (2, 6):
	FAILING_TESTS += [
		# bunch of SSLError: [Errno 1] _ssl.c:504: error:14090086:SSL routines:SSL3_GET_SERVER_CERTIFICATE:certificate verify failed
		# seems to be Python/OpenSSL problem, not gevent's
		'monkey_test --Event test_ssl.py',
		'monkey_test test_ssl.py',
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


if sys.version_info[:2] == (2, 5):
    # no idea
    FAILING_TESTS += [
        'test_urllib2net.py',
        'test_timeout.py',
        'FLAKY test_urllib2_localnet.py',
        'test_urllib2net.py',
        'test__threading_vs_settrace.py',
        'test__example_portforwarder.py',
        'test__socket_close.py',
        'test_timeout.py',
    ]


if __name__ == '__main__':
    import pprint
    pprint.pprint(FAILING_TESTS)
