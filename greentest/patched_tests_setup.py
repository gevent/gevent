
# By default, test cases are expected to switch and emit warnings if there was none
# If a test is found in this list, it's expected not to switch.
switch_not_expected = '''test_select.SelectTestCase.test_error_conditions
test_ftplib.TestFTPClass.test_all_errors
test_ftplib.TestFTPClass.test_getwelcome
test_ftplib.TestFTPClass.test_sanitize
test_ftplib.TestFTPClass.test_set_pasv
test_ftplib.TestIPv6Environment.test_af'''.split()

disabled_tests = [
    # uses signal module which does not work with gevent (use gevent.signal())
    'test_socket.TCPTimeoutTest.testInterruptedTimeout',

    # uses some internal C API of threads not available when threads are emulated with greenlets
    'test_threading.ThreadTests.test_PyThreadState_SetAsyncExc',

    # access _sock.gettimeout() which is always in non-blocking mode
    'test_urllib2net.TimeoutTest.test_ftp_no_timeout',
    'test_urllib2net.TimeoutTest.test_ftp_timeout',
    'test_urllib2net.TimeoutTest.test_http_no_timeout',
    'test_urllib2net.TimeoutTest.test_http_timeout',

    # this test seems to have a bug which makes it fail with error: (107, 'Transport endpoint is not connected')
    # (they create TCP socket, not UDP)
    'test_socket.UDPTimeoutTest.testUDPTimeout'
]

import sys, re

def disable_tests_in_the_source(source, name):
    my_disabled_tests = [x for x in disabled_tests if x.startswith(name + '.')]
    if not my_disabled_tests:
        return source
    for test in my_disabled_tests:
        # XXX ignoring TestCase class name
        testcase = test.split('.')[-1]
        source, n = re.subn(testcase, 'XXX' + testcase, source)
        print >> sys.stderr, 'Removed %s (%d)' % (testcase, n)
    return source

