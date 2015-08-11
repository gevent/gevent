#!/usr/bin/python
# -*- coding: utf-8 -*-
import six
import re
import greentest
import socket
from time import time
import gevent
import gevent.socket as gevent_socket
from util import log
from six import xrange


resolver = gevent.get_hub().resolver
log('Resolver: %s', resolver)

if getattr(resolver, 'pool', None) is not None:
    resolver.pool.size = 1


assert gevent_socket.gaierror is socket.gaierror
assert gevent_socket.error is socket.error

DEBUG = False


def _run(function, *args):
    try:
        result = function(*args)
        assert not isinstance(result, BaseException), repr(result)
        return result
    except Exception as ex:
        return ex


def format_call(function, args):
    args = repr(args)
    if args.endswith(',)'):
        args = args[:-2] + ')'
    try:
        module = function.__module__.replace('gevent.socket', 'gevent').replace('_socket', 'stdlib')
        name = function.__name__
        return '%s:%s%s' % (module, name, args)
    except AttributeError:
        return function + args


def log_fresult(result, seconds):
    if isinstance(result, Exception):
        msg = '  -=>  raised %r' % (result, )
    else:
        msg = '  -=>  returned %r' % (result, )
    time_ms = ' %.2fms' % (seconds * 1000.0, )
    space = 80 - len(msg) - len(time_ms)
    if space > 0:
        space = ' ' * space
    else:
        space = ''
    log(msg + space + time_ms)


def run(function, *args):
    if DEBUG:
        log(format_call(function, args))
    delta = time()
    result = _run(function, *args)
    delta = time() - delta
    if DEBUG:
        log_fresult(result, delta)
    return result, delta


def log_call(result, time, function, *args):
    log(format_call(function, args))
    log_fresult(result, time)


def compare_relaxed(a, b):
    """
    >>> compare_relaxed('2a00:1450:400f:801::1010', '2a00:1450:400f:800::1011')
    True

    >>> compare_relaxed('2a00:1450:400f:801::1010', '2aXX:1450:400f:900::1011')
    False

    >>> compare_relaxed('2a00:1450:4016:800::1013', '2a00:1450:4008:c01::93')
    True

    >>> compare_relaxed('2001:470::e852:4a38:9d7f:0', '2001:470:6d00:1c:1::d00')
    True

    >>> compare_relaxed('2001:470:4147:4943:6161:6161:2e74:6573', '2001:470::')
    True

    >>> compare_relaxed('2607:f8b0:6708:24af:1fd:700:60d4:4af', '2607:f8b0:2d00::f000:0')
    True

    >>> compare_relaxed('a.google.com', 'b.google.com')
    True

    >>> compare_relaxed('a.google.com', 'a.gevent.org')
    False
    """
    # IPv6 address from different requests might be different
    a_segments = a.count(':')
    b_segments = b.count(':')
    if a_segments and b_segments:
        if a_segments == b_segments and a_segments in (4, 5, 6, 7):
            return True
        if a.rstrip(':').startswith(b.rstrip(':')) or b.rstrip(':').startswith(a.rstrip(':')):
            return True
        if a_segments >= 2 and b_segments >= 2 and a.split(':')[:2] == b.split(':')[:2]:
            return True

    return a.split('.', 1)[-1] == b.split('.', 1)[-1]


def contains_5tuples(lst):
    for item in lst:
        if not (isinstance(item, tuple) and len(item) == 5):
            return False
    return True


def relaxed_is_equal(a, b):
    """
    >>> relaxed_is_equal([(10, 1, 6, '', ('2a00:1450:400f:801::1010', 80, 0, 0))], [(10, 1, 6, '', ('2a00:1450:400f:800::1011', 80, 0, 0))])
    True

    >>> relaxed_is_equal([1, '2'], (1, '2'))
    False

    >>> relaxed_is_equal([1, '2'], [1, '2'])
    True

    >>> relaxed_is_equal(('wi-in-x93.1e100.net', 'http'), ('we-in-x68.1e100.net', 'http'))
    True
    """
    if type(a) is not type(b):
        return False
    if a == b:
        return True
    if isinstance(a, six.string_types):
        return compare_relaxed(a, b)
    if len(a) != len(b):
        return False
    if contains_5tuples(a) and contains_5tuples(b):
        # getaddrinfo results
        a = sorted(a)
        b = sorted(b)
    return all(relaxed_is_equal(x, y) for (x, y) in zip(a, b))


def add(klass, hostname, name=None):

    call = callable(hostname)

    if name is None:
        if call:
            name = hostname.__name__
        else:
            name = re.sub('[^\w]+', '_', repr(hostname))
        assert name, repr(hostname)

    def test1(self):
        x = hostname() if call else hostname
        self._test('getaddrinfo', x, 'http')
    test1.__name__ = 'test_%s_getaddrinfo' % name
    setattr(klass, test1.__name__, test1)

    def test2(self):
        x = hostname() if call else hostname
        ipaddr = self._test('gethostbyname', x)
        if not isinstance(ipaddr, Exception):
            self._test('gethostbyaddr', ipaddr)
    test2.__name__ = 'test_%s_gethostbyname' % name
    setattr(klass, test2.__name__, test2)

    def test3(self):
        x = hostname() if call else hostname
        self._test('gethostbyname_ex', x)
    test3.__name__ = 'test_%s_gethostbyname_ex' % name
    setattr(klass, test3.__name__, test3)

    def test4(self):
        x = hostname() if call else hostname
        self._test('gethostbyaddr', x)
    test4.__name__ = 'test_%s_gethostbyaddr' % name
    setattr(klass, test4.__name__, test4)

    def test5(self):
        x = hostname() if call else hostname
        self._test('getnameinfo', (x, 80), 0)
    test5.__name__ = 'test_%s_getnameinfo' % name
    setattr(klass, test5.__name__, test5)


class TestCase(greentest.TestCase):

    __timeout__ = 30
    switch_expected = None

    def should_log_results(self, result1, result2):
        if isinstance(result1, BaseException) and isinstance(result2, BaseException):
            return type(result1) is not type(result2)
        return repr(result1) != repr(result2)

    def _test(self, func, *args):
        gevent_func = getattr(gevent_socket, func)
        real_func = getattr(socket, func)
        real_result, time_real = run(real_func, *args)
        gevent_result, time_gevent = run(gevent_func, *args)
        if not DEBUG and self.should_log_results(real_result, gevent_result):
            log('')
            log_call(real_result, time_real, real_func, *args)
            log_call(gevent_result, time_gevent, gevent_func, *args)
        self.assertEqualResults(real_result, gevent_result, func, args)

        if time_gevent > time_real + 0.01 and time_gevent > 0.02:
            msg = 'gevent:%s%s took %dms versus %dms stdlib' % (func, args, time_gevent * 1000.0, time_real * 1000.0)

            if time_gevent > time_real + 1:
                word = 'VERY'
            else:
                word = 'quite'

            log('\nWARNING: %s slow: %s', word, msg)

        return gevent_result

    def _normalize_result(self, result):
        return result

    def assertEqualResults(self, real_result, gevent_result, func, args):
        errors = (socket.gaierror, socket.herror, TypeError)
        if isinstance(real_result, errors) and isinstance(gevent_result, errors):
            if type(real_result) is not type(gevent_result):
                log('WARNING: error type mismatch: %r (gevent) != %r (stdlib)', gevent_result, real_result)
            return

        real_result = self._normalize_result(real_result)
        gevent_result = self._normalize_result(gevent_result)

        real_result_repr = repr(real_result)
        gevent_result_repr = repr(gevent_result)
        if real_result_repr == gevent_result_repr:
            return
        if relaxed_is_equal(gevent_result, real_result):
            return

        # From 2.7 on, assertEqual does a better job highlighting the results than we would
        # because it calls assertSequenceEqual, which highlights the exact
        # difference in the tuple
        msg = format_call(func, args)
        self.assertEqual((msg, gevent_result), (msg, real_result))


class TestTypeError(TestCase):
    pass

add(TestTypeError, None)
add(TestTypeError, 25)


class TestHostname(TestCase):
    pass

add(TestHostname, socket.gethostname)


class TestLocalhost(TestCase):
    # certain tests in test_patched_socket.py only work if getaddrinfo('localhost') does not switch
    # (e.g. NetworkConnectionAttributesTest.testSourceAddress)
    pass
    #switch_expected = False

add(TestLocalhost, 'localhost')
add(TestLocalhost, 'ip6-localhost')


class TestNonexistent(TestCase):
    pass

add(TestNonexistent, 'nonexistentxxxyyy')


class Test1234(TestCase):
    pass

add(Test1234, '1.2.3.4')


class Test127001(TestCase):
    pass

add(Test127001, '127.0.0.1')


class TestBroadcast(TestCase):
    switch_expected = False


add(TestBroadcast, '<broadcast>')


class TestEtcHosts(TestCase):
    pass

try:
    etc_hosts = open('/etc/hosts').read()
except IOError:
    etc_hosts = ''

for ip, host in re.findall(r'^\s*(\d+\.\d+\.\d+\.\d+)\s+([^\s]+)', etc_hosts, re.M)[:10]:
    add(TestEtcHosts, host)
    add(TestEtcHosts, ip)
    del host, ip


class TestGeventOrg(TestCase):

    HOSTNAME = 'www.gevent.org'

# For this test to work correctly, it needs to resolve to
# an address with a single A record; round-robin DNS and multiple A records
# may mess it up (subsequent requests---and we always make two---may return
# unequal results). We used to use gevent.org, but that now has multiple A records;
# trying www.gevent.org which is a CNAME to readthedocs.org.
add(TestGeventOrg, TestGeventOrg.HOSTNAME)


class TestFamily(TestCase):

    @classmethod
    def getresult(cls):
        if not hasattr(cls, '_result'):
            cls._result = getattr(socket, 'getaddrinfo')(TestGeventOrg.HOSTNAME, None)
        return cls._result

    def assert_error(self, error, function, *args):
        try:
            result = function(*args)
            raise AssertionError('%s: Expected to raise %s, instead returned %r' % (function, error, result))
        except Exception as ex:
            if isinstance(error, six.string_types):
                repr_error = error
            else:
                repr_error = repr(error)
                if type(ex) is not type(error):
                    raise
            if repr(ex) == repr_error:
                return
            raise

    def test_inet(self):
        self.assertEqual(gevent_socket.getaddrinfo(TestGeventOrg.HOSTNAME, None, socket.AF_INET), self.getresult())

    def test_unspec(self):
        self.assertEqual(gevent_socket.getaddrinfo(TestGeventOrg.HOSTNAME, None, socket.AF_UNSPEC), self.getresult())

    def test_badvalue(self):
        self._test('getaddrinfo', TestGeventOrg.HOSTNAME, None, 255)
        self._test('getaddrinfo', TestGeventOrg.HOSTNAME, None, 255000)
        self._test('getaddrinfo', TestGeventOrg.HOSTNAME, None, -1)

    def test_badtype(self):
        self._test('getaddrinfo', TestGeventOrg.HOSTNAME, 'x')


class Test_getaddrinfo(TestCase):

    def _test_getaddrinfo(self, *args):
        self._test('getaddrinfo', *args)

    def test_80(self):
        self._test_getaddrinfo(TestGeventOrg.HOSTNAME, 80)

    def test_int_string(self):
        self._test_getaddrinfo(TestGeventOrg.HOSTNAME, '80')

    def test_0(self):
        self._test_getaddrinfo(TestGeventOrg.HOSTNAME, 0)

    def test_http(self):
        self._test_getaddrinfo(TestGeventOrg.HOSTNAME, 'http')

    def test_notexistent_tld(self):
        self._test_getaddrinfo('myhost.mytld', 53)

    def test_notexistent_dot_com(self):
        self._test_getaddrinfo('sdfsdfgu5e66098032453245wfdggd.com', 80)

    def test1(self):
        return self._test_getaddrinfo(TestGeventOrg.HOSTNAME, 52, socket.AF_UNSPEC, socket.SOCK_STREAM, 0, 0)

    def test2(self):
        return self._test_getaddrinfo(TestGeventOrg.HOSTNAME, 53, socket.AF_INET, socket.SOCK_DGRAM, 17)

    def test3(self):
        return self._test_getaddrinfo('google.com', 'http', socket.AF_INET6)


class TestInternational(TestCase):
    pass

add(TestInternational, u'президент.рф', 'russian')
add(TestInternational, u'президент.рф'.encode('idna'), 'idna')


class TestInterrupted_gethostbyname(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        with gevent.Timeout(timeout, False):
            for index in xrange(1000000):
                try:
                    gevent_socket.gethostbyname('www.x%s.com' % index)
                except socket.error:
                    pass
            raise AssertionError('Timeout was not raised')

    def cleanup(self):
        gevent.get_hub().threadpool.join()


# class TestInterrupted_getaddrinfo(greentest.GenericWaitTestCase):
#
#     def wait(self, timeout):
#         with gevent.Timeout(timeout, False):
#             for index in range(1000):
#                 try:
#                     gevent_socket.getaddrinfo('www.a%s.com' % index, 'http')
#                 except socket.gaierror:
#                     pass


class TestBadName(TestCase):
    pass

add(TestBadName, 'xxxxxxxxxxxx')


class TestBadIP(TestCase):
    pass

add(TestBadIP, '1.2.3.400')


class Test_getnameinfo_127001(TestCase):

    def test(self):
        assert gevent_socket.getnameinfo is not socket.getnameinfo
        self._test('getnameinfo', ('127.0.0.1', 80), 0)

    def test_DGRAM(self):
        self._test('getnameinfo', ('127.0.0.1', 779), 0)
        self._test('getnameinfo', ('127.0.0.1', 779), socket.NI_DGRAM)

    def test_NOFQDN(self):
        # I get ('localhost', 'www') with _socket but ('localhost.localdomain', 'www') with gevent.socket
        self._test('getnameinfo', ('127.0.0.1', 80), socket.NI_NOFQDN)

    def test_NAMEREQD(self):
        self._test('getnameinfo', ('127.0.0.1', 80), socket.NI_NAMEREQD)


class Test_getnameinfo_geventorg(TestCase):

    def test_NUMERICHOST(self):
        self._test('getnameinfo', (TestGeventOrg.HOSTNAME, 80), 0)
        self._test('getnameinfo', (TestGeventOrg.HOSTNAME, 80), socket.NI_NUMERICHOST)

    def test_NUMERICSERV(self):
        self._test('getnameinfo', (TestGeventOrg.HOSTNAME, 80), socket.NI_NUMERICSERV)

    def test_domain1(self):
        self._test('getnameinfo', (TestGeventOrg.HOSTNAME, 80), 0)

    def test_domain2(self):
        self._test('getnameinfo', ('www.gevent.org', 80), 0)

    def test_port_zero(self):
        self._test('getnameinfo', ('www.gevent.org', 0), 0)


class Test_getnameinfo_fail(TestCase):

    def test_port_string(self):
        self._test('getnameinfo', ('www.gevent.org', 'http'), 0)

    def test_bad_flags(self):
        self._test('getnameinfo', ('127.0.0.1', 80), 55555555)


class TestInvalidPort(TestCase):

    def test1(self):
        self._test('getnameinfo', ('www.gevent.org', -1), 0)

    def test2(self):
        self._test('getnameinfo', ('www.gevent.org', None), 0)

    def test3(self):
        self._test('getnameinfo', ('www.gevent.org', 'x'), 0)

    def test4(self):
        self._test('getnameinfo', ('www.gevent.org', 65536), 0)


if __name__ == '__main__':
    greentest.main()
