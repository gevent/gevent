#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import with_statement
import sys
import re
import traceback
import greentest
import socket
import gevent
import gevent.socket as gevent_socket


# also test: '<broadcast>'


accept_results = [
                  # Python's socketmodule.c randomly chooses between gaierror and herror when raising an exception
                  # There are also a number of error code that are mapped to ARES_ENOTFOUND

                  ("gaierror(4, 'ARES_ENOTFOUND: Domain name not found')",
                   "herror(1, 'Unknown host')"),

                  ("gaierror(4, 'ARES_ENOTFOUND: Domain name not found')",
                   "gaierror(-2, 'Name or service not known')"),

                  ("gaierror(4, 'ARES_ENOTFOUND: Domain name not found')",
                   "gaierror(-5, 'No address associated with hostname')"),

                  ("gaierror(1, 'ARES_ENODATA: DNS server returned answer with no data')",
                   "herror(4, 'No address associated with name')"),

                  ("gaierror(1, 'ARES_ENODATA: DNS server returned answer with no data')",
                   "gaierror(-5, 'No address associated with hostname')"),

                  # _socket.gethostbyname_ex('\x00') checks for zeroes and raises TypeError
                  # but it's not worth the trouble
                  ("gaierror(1, 'ARES_ENODATA: DNS server returned answer with no data')",
                   "TypeError('must be string without null bytes, not str',)",),

                  # in some cases gevent error messages are better:
                  ("gaierror(-1, 'Bad value for ai_flags: 0x34fb5e0')",
                   "gaierror(-1, 'Bad value for ai_flags')"),

                  ("gaierror(-8, 'Invalid value for port: -1')",
                   "gaierror(-8, 'Servname not supported for ai_socktype')"),

                  ("gaierror(-8, 'Invalid value for port: 65536')",
                   "gaierror(-8, 'Servname not supported for ai_socktype')"),

                  # in some cases the error is different, but that's OK
                  ("error('sockaddr resolved to multiple addresses',)",
                   "TypeError('must be string, not None',)")
]


assert gevent_socket.gaierror is socket.gaierror
assert gevent_socket.error is socket.error

VERBOSE = sys.argv.count('-v') + 2 * sys.argv.count('-vv')
PASS = True
LOGFILE = sys.stderr


def log(s, *args, **kwargs):
    newline = kwargs.pop('newline', True)
    assert not kwargs, kwargs
    if not VERBOSE:
        return
    try:
        s = s % args
    except Exception:
        traceback.print_exc()
        s = '%s %r' % (s, args)
    if newline:
        s += '\n'
    LOGFILE.write(s)


def _run(function, *args):
    try:
        result = function(*args)
        assert not isinstance(result, Exception), repr(result)
        return result
    except Exception:
        return sys.exc_info()[1]


def log_fcall(function, args):
    args = repr(args)
    if args.endswith(',)'):
        args = args[:-2] + ')'
    log('\n%7s.%s%s',
        function.__module__.replace('gevent.socket', 'gevent'),
        function.__name__,
        args,
        newline=False)


def log_fresult(result):
    if isinstance(result, Exception):
        log(' -> raised %r', result)
    else:
        log(' -> returned %r', result)


def run(function, *args):
    if VERBOSE >= 2:
        log_fcall(function, args)
    result = _run(function, *args)
    if VERBOSE >= 2:
        log_fresult(result)
    return result


def log_call(result, function, *args):
    log_fcall(function, args)
    log_fresult(result)


class TestCase(greentest.TestCase):

    __timeout__ = 15

    def _test(self, func, *args):
        gevent_func = getattr(gevent_socket, func)
        real_func = getattr(socket, func)
        result = run(gevent_func, *args)
        real_result = run(real_func, *args)
        if VERBOSE == 1 and repr(result) != repr(real_result):
            # slightly less verbose mode: only print the results that are different
            log_call(result, gevent_func, *args)
            log_call(real_result, real_func, *args)
            log('')
        elif VERBOSE >= 2:
            log('')
        self.assertEqualResults(real_result, result)
        return result

    def _test_all(self, hostname):
        self._test('getaddrinfo', hostname, 'http')
        ipaddr = self._test('gethostbyname', hostname)
        self._test('gethostbyname_ex', hostname)
        if not isinstance(ipaddr, Exception):
            self._test('gethostbyaddr', ipaddr)
        self._test('gethostbyaddr', hostname)
        self._test('getnameinfo', (hostname, 80), 0)

    def assertEqualResults(self, real_result, gevent_result):
        if type(real_result) is TypeError and type(gevent_result) is TypeError:
            return
        real_result = repr(real_result)
        gevent_result = repr(gevent_result)
        if real_result == gevent_result:
            return
        if (gevent_result, real_result) in accept_results:
            return
        raise AssertionError('%s != %s' % (gevent_result, real_result))


def get_test(ip, host):

    def test(self):
        self._test_all(host)
    test.__name__ = 'test_' + re.sub('[^\w]', '_', host)

    return test


class TestLocal(TestCase):

    switch_expected = False

    def test_hostname(self):
        assert socket.gethostname is gevent_socket.gethostname
        hostname = socket.gethostname()
        self._test_all(hostname)

    def test_localhost_getaddrinfo(self):
        # certain tests in test_patched_socket.py only work if getaddrinfo('localhost') does not switch
        # (e.g. NetworkConnectionAttributesTest.testSourceAddress)
        self.switch_expected = False
        gevent_socket.getaddrinfo('localhost', 80)

    def test_localhost(self):
        self._test_all('localhost')

    def test_127_0_0_1(self):
        self._test_all('127.0.0.1')

    def test_1_2_3_4(self):
        self._test_all('1.2.3.4')

    def test_notexistent(self):
        self._test_all('notexistent')

    # <broadcast>, 127.0.0.1 special-cased in socketmodule.c?

    def test_None(self):
        self.switch_expected = False
        self._test_all(None)

    def test_25(self):
        self.switch_expected = False
        self._test_all(25)

    try:
        etc_hosts = open('/etc/hosts').read()
    except IOError:
        etc_hosts = ''

    for ip, host in re.findall(r'^\s*(\d+\.\d+\.\d+\.\d+)\s+([^\s]+)', etc_hosts, re.M)[:10]:
        func = get_test(ip, host)
        print 'Adding %s' % func.__name__
        locals()[func.__name__] = func
        del func


class TestSimple(TestCase):

    def test_gethostbyname(self):
        gevent_socket.gethostbyname('gevent.org')
        #self._test('gethostbyname', 'gevent.org')

    def test_gethostbyname_ex(self):
        self._test('gethostbyname_ex', 'gevent.org')


class TestFamily(TestCase):

    @classmethod
    def getresult(cls):
        if not hasattr(cls, '_result'):
            cls._result = getattr(socket, 'getaddrinfo')('gevent.org', None)
        return cls._result

    def assert_error(self, error, function, *args):
        try:
            result = function(*args)
            raise AssertionError('%s: Expected to raise %s, instead returned %r' % (function, error, result))
        except Exception, ex:
            if isinstance(error, basestring):
                repr_error = error
            else:
                repr_error = repr(error)
                if type(ex) is not type(error):
                    raise
            if repr(ex) == repr_error:
                return
            raise

    def test_inet(self):
        self.assertEqual(gevent_socket.getaddrinfo('gevent.org', None, socket.AF_INET), self.getresult())

    def test_inet6(self):
        expected = socket.gaierror(1, 'ARES_ENODATA: DNS server returned answer with no data')
        self.assert_error(expected, gevent_socket.getaddrinfo, 'gevent.org', None, socket.AF_INET6)

    def test_unspec(self):
        self.assertEqual(gevent_socket.getaddrinfo('gevent.org', None, socket.AF_UNSPEC), self.getresult())

    def test_badvalue(self):
        self.switch_expected = False
        self._test('getaddrinfo', 'gevent.org', None, 255)
        self._test('getaddrinfo', 'gevent.org', None, 255000)
        self._test('getaddrinfo', 'gevent.org', None, -1)

    def test_badtype(self):
        self.switch_expected = False
        self._test('getaddrinfo', 'gevent.org', 'x')


class Test_getaddrinfo(TestCase):

    switch_expected = True

    def _test_getaddrinfo(self, *args):
        self._test('getaddrinfo', *args)

    def test_80(self):
        self._test_getaddrinfo('gevent.org', 80)

    def test_int_string(self):
        self._test_getaddrinfo('gevent.org', '80')

    def test_0(self):
        self._test_getaddrinfo('gevent.org', 0)

    def test_http(self):
        self._test_getaddrinfo('gevent.org', 'http')

    def test_notexistent_tld(self):
        self._test_getaddrinfo('myhost.mytld', 53)

    def test_notexistent_dot_com(self):
        self._test_getaddrinfo('sdfsdfgu5e66098032453245wfdggd.com', 80)

    def test1(self):
        return self._test_getaddrinfo('gevent.org', 52, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, 0)

    def test2(self):
        return self._test_getaddrinfo('gevent.org', 53, socket.AF_INET, socket.SOCK_DGRAM, 17)

    def test3(self):
        return self._test_getaddrinfo('google.com', 'http', socket.AF_INET6)


class TestInternational(TestCase):
    domain = u'президент.рф'

    def test(self):
        self._test_all(self.domain)

    def test_idna(self):
        self._test('gethostbyname', self.domain.encode('idna'))

    def test_getaddrinfo(self):
        self._test('getaddrinfo', self.domain, 'http')


class TestInterrupted_gethostbyname(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        with gevent.Timeout(timeout, False):
            for index in range(1000):
                try:
                    gevent_socket.gethostbyname('www.x%s.com' % index)
                except socket.error:
                    pass


# class TestInterrupted_getaddrinfo(greentest.GenericWaitTestCase):
#
#     def wait(self, timeout):
#         with gevent.Timeout(timeout, False):
#             for index in range(1000):
#                 try:
#                     gevent_socket.getaddrinfo('www.a%s.com' % index, 'http')
#                 except socket.gaierror:
#                     pass


class TestIPv6(TestCase):

    # host that only has AAAA record
    host = 'aaaa.test-ipv6.com'

    def test(self):
        self._test_all(self.host)

    def test_(self):
        self._test('getaddrinfo', self.host, 'http')

    def test_inet(self):
        self._test('getaddrinfo', self.host, None, socket.AF_INET)

    def test_inet6(self):
        self._test('getaddrinfo', self.host, None, socket.AF_INET6)

    def test_unspec(self):
        self._test('getaddrinfo', self.host, None, socket.AF_UNSPEC)


class TestIPv6_ds(TestIPv6):

    # host that has both A and AAAA records
    host = 'ds.test-ipv6.com'


class TestBadIP(TestCase):

    def test_name(self):
        self._test_all('xxxxxxxxx')

    def test_ip(self):
        self._test_all('1.2.3.400')


class Test_getnameinfo(TestCase):

    def test(self):
        assert gevent_socket.getnameinfo is not socket.getnameinfo
        self._test('getnameinfo', ('127.0.0.1', 80), 0)

    def test_DGRAM(self):
        self._test('getnameinfo', ('127.0.0.1', 779), 0)
        self._test('getnameinfo', ('127.0.0.1', 779), socket.NI_DGRAM)

    def test_NOFQDN(self):
        # I get ('localhost', 'www') with _socket but ('localhost.localdomain', 'www') with gevent.socket
        self._test('getnameinfo', ('127.0.0.1', 80), socket.NI_NOFQDN)

    def test_NUMERICHOST(self):
        self._test('getnameinfo', ('gevent.org', 80), 0)
        self._test('getnameinfo', ('gevent.org', 80), socket.NI_NUMERICHOST)

    def test_NUMERICSERV(self):
        self._test('getnameinfo', ('gevent.org', 80), socket.NI_NUMERICSERV)

    def test_NAMEREQD(self):
        self._test('getnameinfo', ('127.0.0.1', 80), socket.NI_NAMEREQD)

    def test_domain1(self):
        self._test('getnameinfo', ('gevent.org', 80), 0)

    def test_domain2(self):
        self._test('getnameinfo', ('www.gevent.org', 80), 0)

    def test_port_string(self):
        self._test('getnameinfo', ('www.gevent.org', 'http'), 0)

    def test_port_zero(self):
        self._test('getnameinfo', ('www.gevent.org', 0), 0)


class Test_getnameinfo_fail(TestCase):
    switch_expected = False

    def test_bad_flags(self):
        self._test('getnameinfo', ('127.0.0.1', 80), 55555555)

    def test_invalid_port(self):
        self._test('getnameinfo', ('www.gevent.org', -1), 0)
        self._test('getnameinfo', ('www.gevent.org', None), 0)
        self._test('getnameinfo', ('www.gevent.org', 'x'), 0)
        self._test('getnameinfo', ('www.gevent.org', 65536), 0)


if __name__ == '__main__':
    greentest.main()
