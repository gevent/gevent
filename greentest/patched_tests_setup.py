import sys
import re

# By default, test cases are expected to switch and emit warnings if there was none
# If a test is found in this list, it's expected not to switch.
tests = '''test_select.SelectTestCase.test_error_conditions
test_ftplib.TestFTPClass.test_all_errors
test_ftplib.TestFTPClass.test_getwelcome
test_ftplib.TestFTPClass.test_sanitize
test_ftplib.TestFTPClass.test_set_pasv
test_ftplib.TestIPv6Environment.test_af
test_socket.TestExceptions.testExceptionTree
test_socket.Urllib2FileobjectTest.testClose
test_socket.TestLinuxAbstractNamespace.testLinuxAbstractNamespace
test_socket.TestLinuxAbstractNamespace.testMaxName
test_socket.TestLinuxAbstractNamespace.testNameOverflow
test_socket.GeneralModuleTests.*
'''

tests = [x.strip().replace('\.', '\\.').replace('*', '.*?') for x in  tests.split('\n') if x.strip()]
tests = re.compile('^%s$' % '|'.join(tests))


def get_switch_expected(fullname):
    """
    >>> get_switch_expected('test_select.SelectTestCase.test_error_conditions')
    False
    >>> get_switch_expected('test_socket.GeneralModuleTests.testCrucialConstants')
    False
    >>> get_switch_expected('test_socket.SomeOtherTest.testHello')
    True
    """
    if tests.match(fullname) is not None:
        print (fullname)
        return False
    return True


disabled_tests = \
    [ 'test_threading.ThreadTests.test_PyThreadState_SetAsyncExc'
    # uses some internal C API of threads not available when threads are emulated with greenlets

    , 'test_urllib2net.TimeoutTest.test_ftp_no_timeout'
    , 'test_urllib2net.TimeoutTest.test_ftp_timeout'
    , 'test_urllib2net.TimeoutTest.test_http_no_timeout'
    , 'test_urllib2net.TimeoutTest.test_http_timeout'
    # access _sock.gettimeout() which is always in non-blocking mode

    , 'test_socket.UDPTimeoutTest.testUDPTimeout'
    # has a bug which makes it fail with error: (107, 'Transport endpoint is not connected')
    # (it creates a TCP socket, not UDP)

    , 'test_socket.GeneralModuleTests.testRefCountGetNameInfo'
    # fails with "socket.getnameinfo loses a reference" while the reference is only "lost"
    # because it is referenced by the traceback - any Python function would lose a reference like that.
    # the original getnameinfo does not lose it because it's in C.

    , 'test_socket.NetworkConnectionNoServer.test_create_connection_timeout'
    # replaces socket.socket with MockSocket and then calls create_connection.
    # this unfortunately does not work with monkey patching, because gevent.socket.create_connection
    # is bound to gevent.socket.socket and updating socket.socket does not affect it.
    # this issues also manifests itself when not monkey patching DNS: http://code.google.com/p/gevent/issues/detail?id=54
    # create_connection still uses gevent.socket.getaddrinfo while it should be using socket.getaddrinfo

    , 'test_asyncore.BaseTestAPI.test_handle_expt'
    # sends some OOB data and expect it to be detected as such; gevent.select.select does not support that

    , 'test_signal.WakeupSignalTests.test_wakeup_fd_early'
    # expects time.sleep() to return prematurely in case of a signal;
    # gevent.sleep() is better than that and does not get interrupted (unless signal handler raises an error)

    , 'test_signal.WakeupSignalTests.test_wakeup_fd_during'
    # expects select.select() to raise select.error(EINTR, 'interrupted system call')
    # gevent.select.select() does not get interrupted (unless signal handler raises an error)
    # maybe it should?
]

if sys.version_info[:2] < (2, 7):
    # On Python 2.6, this test fails even without monkey patching
    disabled_tests.append('test_threading.ThreadTests.test_foreign_thread')


def disable_tests_in_source(source, name):
    my_disabled_tests = [x for x in disabled_tests if x.startswith(name + '.')]
    if not my_disabled_tests:
        return source
    for test in my_disabled_tests:
        # XXX ignoring TestCase class name
        testcase = test.split('.')[-1]
        source, n = re.subn(testcase, 'XXX' + testcase, source)
        print >> sys.stderr, 'Removed %s (%d)' % (testcase, n)
    return source
