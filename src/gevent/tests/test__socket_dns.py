#!/usr/bin/python
# -*- coding: utf-8 -*-
# pylint:disable=broad-except
import gevent
from gevent import monkey

import os
import re
import gevent.testing as greentest
import unittest
import socket
from time import time
import traceback
import gevent.socket as gevent_socket
from gevent.testing.util import log
from gevent.testing import six
from gevent.testing.six import xrange


resolver = gevent.get_hub().resolver
log('Resolver: %s', resolver)

if getattr(resolver, 'pool', None) is not None:
    resolver.pool.size = 1

from gevent.testing.sysinfo import RESOLVER_NOT_SYSTEM
from gevent.testing.sysinfo import RESOLVER_DNSPYTHON
from gevent.testing.sysinfo import PY2
import gevent.testing.timing


assert gevent_socket.gaierror is socket.gaierror
assert gevent_socket.error is socket.error

DEBUG = os.getenv('GEVENT_DEBUG', '') == 'trace'


def _run(function, *args):
    try:
        result = function(*args)
        assert not isinstance(result, BaseException), repr(result)
        return result
    except Exception as ex:
        if DEBUG:
            traceback.print_exc()
        return ex


def format_call(function, args):
    args = repr(args)
    if args.endswith(',)'):
        args = args[:-2] + ')'
    try:
        module = function.__module__.replace('gevent._socketcommon', 'gevent')
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


def log_call(result, runtime, function, *args):
    log(format_call(function, args))
    log_fresult(result, runtime)


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
    try:
        if len(a) != len(b):
            return False
    except TypeError:
        return False
    if contains_5tuples(a) and contains_5tuples(b):
        # getaddrinfo results
        a = sorted(a)
        b = sorted(b)
    return all(relaxed_is_equal(x, y) for (x, y) in zip(a, b))


def add(klass, hostname, name=None,
        skip=None, skip_reason=None):

    call = callable(hostname)

    def _setattr(k, n, func):
        if skip:
            func = greentest.skipIf(skip, skip_reason,)(func)
        if not hasattr(k, n):
            setattr(k, n, func)

    if name is None:
        if call:
            name = hostname.__name__
        else:
            name = re.sub(r'[^\w]+', '_', repr(hostname))
        assert name, repr(hostname)

    def test1(self):
        x = hostname() if call else hostname
        self._test('getaddrinfo', x, 'http')
    test1.__name__ = 'test_%s_getaddrinfo' % name
    _setattr(klass, test1.__name__, test1)

    def test2(self):
        x = hostname() if call else hostname
        ipaddr = self._test('gethostbyname', x)
        if not isinstance(ipaddr, Exception):
            self._test('gethostbyaddr', ipaddr)
    test2.__name__ = 'test_%s_gethostbyname' % name
    _setattr(klass, test2.__name__, test2)

    def test3(self):
        x = hostname() if call else hostname
        self._test('gethostbyname_ex', x)
    test3.__name__ = 'test_%s_gethostbyname_ex' % name
    _setattr(klass, test3.__name__, test3)

    def test4(self):
        x = hostname() if call else hostname
        self._test('gethostbyaddr', x)
    test4.__name__ = 'test_%s_gethostbyaddr' % name
    _setattr(klass, test4.__name__, test4)

    def test5(self):
        x = hostname() if call else hostname
        self._test('getnameinfo', (x, 80), 0)
    test5.__name__ = 'test_%s_getnameinfo' % name
    _setattr(klass, test5.__name__, test5)


class TestCase(greentest.TestCase):

    __timeout__ = 30
    switch_expected = None
    verbose_dns = False

    def should_log_results(self, result1, result2):
        if not self.verbose_dns:
            return False

        if isinstance(result1, BaseException) and isinstance(result2, BaseException):
            return type(result1) is not type(result2)
        return repr(result1) != repr(result2)

    def _test(self, func, *args):
        gevent_func = getattr(gevent_socket, func)
        real_func = monkey.get_original('socket', func)
        real_result, time_real = run(real_func, *args)
        gevent_result, time_gevent = run(gevent_func, *args)
        if not DEBUG and self.should_log_results(real_result, gevent_result):
            log('')
            log_call(real_result, time_real, real_func, *args)
            log_call(gevent_result, time_gevent, gevent_func, *args)
        self.assertEqualResults(real_result, gevent_result, func)

        if self.verbose_dns and time_gevent > time_real + 0.01 and time_gevent > 0.02:
            msg = 'gevent:%s%s took %dms versus %dms stdlib' % (func, args, time_gevent * 1000.0, time_real * 1000.0)

            if time_gevent > time_real + 1:
                word = 'VERY'
            else:
                word = 'quite'

            log('\nWARNING: %s slow: %s', word, msg)

        return gevent_result

    def _normalize_result(self, result, func_name):
        norm_name = '_normalize_result_' + func_name
        if hasattr(self, norm_name):
            return getattr(self, norm_name)(result)
        return result

    def _normalize_result_gethostbyname_ex(self, result):
        # Often the second and third part of the tuple (hostname, aliaslist, ipaddrlist)
        # can be in different orders if we're hitting different servers,
        # or using the native and ares resolvers due to load-balancing techniques.
        # We sort them.
        if not RESOLVER_NOT_SYSTEM or isinstance(result, BaseException):
            return result
        # result[1].sort() # we wind up discarding this

        # On Py2 in test_russion_gethostbyname_ex, this
        # is actually an integer, for some reason. In TestLocalhost.tets__ip6_localhost,
        # the result isn't this long (maybe an error?).
        try:
            result[2].sort()
        except AttributeError:
            pass
        except IndexError:
            return result
        # On some systems, a random alias is found in the aliaslist
        # by the system resolver, but not by cares, and vice versa. We deem the aliaslist
        # unimportant and discard it.
        # On some systems (Travis CI), the ipaddrlist for 'localhost' can come back
        # with two entries 127.0.0.1 (presumably two interfaces?) for c-ares
        ips = result[2]
        if ips == ['127.0.0.1', '127.0.0.1']:
            ips = ['127.0.0.1']
        # On some systems, the hostname can get caps
        return (result[0].lower(), [], ips)

    def _normalize_result_getaddrinfo(self, result):
        if not RESOLVER_NOT_SYSTEM:
            return result
        # On Python 3, the builtin resolver can return SOCK_RAW results, but
        # c-ares doesn't do that. So we remove those if we find them.
        if hasattr(socket, 'SOCK_RAW') and isinstance(result, list):
            result = [x for x in result if x[1] != socket.SOCK_RAW]
        if isinstance(result, list):
            result.sort()
        return result

    def _normalize_result_gethostbyaddr(self, result):
        if not RESOLVER_NOT_SYSTEM:
            return result

        if isinstance(result, tuple):
            # On some systems, a random alias is found in the aliaslist
            # by the system resolver, but not by cares and vice versa. We deem the aliaslist
            # unimportant and discard it.
            return (result[0], [], result[2])
        return result

    def assertEqualResults(self, real_result, gevent_result, func):
        errors = (socket.gaierror, socket.herror, TypeError)
        if isinstance(real_result, errors) and isinstance(gevent_result, errors):
            if type(real_result) is not type(gevent_result):
                log('WARNING: error type mismatch: %r (gevent) != %r (stdlib)', gevent_result, real_result)
            return

        real_result = self._normalize_result(real_result, func)
        gevent_result = self._normalize_result(gevent_result, func)

        real_result_repr = repr(real_result)
        gevent_result_repr = repr(gevent_result)
        if real_result_repr == gevent_result_repr:
            return
        if relaxed_is_equal(gevent_result, real_result):
            return

        # If we're using the ares resolver, allow the real resolver to generate an
        # error that the ares resolver actually gets an answer to.

        if (
                RESOLVER_NOT_SYSTEM
                and isinstance(real_result, errors)
                and not isinstance(gevent_result, errors)
        ):
            return

        # From 2.7 on, assertEqual does a better job highlighting the results than we would
        # because it calls assertSequenceEqual, which highlights the exact
        # difference in the tuple
        self.assertEqual(real_result, gevent_result)


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
    #switch_expected = False
    # XXX: The above has been commented out for some time. Apparently this isn't the case
    # anymore.

    def _normalize_result_getaddrinfo(self, result):
        if RESOLVER_NOT_SYSTEM:
            # We see that some impls (OS X) return extra results
            # like DGRAM that ares does not.
            return ()
        return super(TestLocalhost, self)._normalize_result_getaddrinfo(result)

    if greentest.RUNNING_ON_TRAVIS and greentest.PY2 and RESOLVER_NOT_SYSTEM:
        def _normalize_result_gethostbyaddr(self, result):
            # Beginning in November 2017 after an upgrade to Travis,
            # we started seeing ares return ::1 for localhost, but
            # the system resolver is still returning 127.0.0.1 under Python 2
            result = super(TestLocalhost, self)._normalize_result_gethostbyaddr(result)
            if isinstance(result, tuple):
                result = (result[0], result[1], ['127.0.0.1'])
            return result


add(
    TestLocalhost, 'ip6-localhost',
    skip=greentest.RUNNING_ON_TRAVIS,
    skip_reason="ares fails here, for some reason, presumably a badly "
    "configured /etc/hosts"
)
add(
    TestLocalhost, 'localhost',
    skip=greentest.RUNNING_ON_TRAVIS,
    skip_reason="Beginning Dec 1 2017, ares started returning ip6-localhost "
    "instead of localhost"
)


class TestNonexistent(TestCase):
    pass

add(TestNonexistent, 'nonexistentxxxyyy')


class Test1234(TestCase):
    pass

add(Test1234, '1.2.3.4')


class Test127001(TestCase):
    pass

add(
    Test127001, '127.0.0.1',
    skip=greentest.RUNNING_ON_TRAVIS,
    skip_reason="Beginning Dec 1 2017, ares started returning ip6-localhost "
    "instead of localhost"
)



class TestBroadcast(TestCase):
    switch_expected = False

    if RESOLVER_NOT_SYSTEM:
        # ares and dnspython raises errors for broadcasthost/255.255.255.255

        @unittest.skip('ares raises errors for broadcasthost/255.255.255.255')
        def test__broadcast__gethostbyaddr(self):
            return

        test__broadcast__gethostbyname = test__broadcast__gethostbyaddr

add(TestBroadcast, '<broadcast>')


from gevent.resolver.dnspython import HostsFile
class SanitizedHostsFile(HostsFile):
    def iter_all_host_addr_pairs(self):
        for name, addr in super(SanitizedHostsFile, self).iter_all_host_addr_pairs():
            if (RESOLVER_NOT_SYSTEM
                    and (name.endswith('local') # ignore bonjour, ares can't find them
                         # ignore common aliases that ares can't find
                         or addr == '255.255.255.255'
                         or name == 'broadcasthost'
                         # We get extra results from some impls, like OS X
                         # it returns DGRAM results
                         or name == 'localhost')):
                continue # pragma: no cover
            if name.endswith('local'):
                # These can only be found if bonjour is running,
                # and are very slow to do so with the system resolver on OS X
                continue
            yield name, addr

@greentest.skipIf(greentest.RUNNING_ON_CI,
                  "This sometimes randomly fails on Travis with ares and on appveyor, beginning Feb 13, 2018")
# Probably due to round-robin DNS,
# since this is not actually the system's etc hosts file.
# TODO: Rethink this. We need something reliable. Go back to using
# the system's etc hosts?
class TestEtcHosts(TestCase):

    MAX_HOSTS = int(os.getenv('GEVENTTEST_MAX_ETC_HOSTS', '10'))

    @classmethod
    def populate_tests(cls):
        hf = SanitizedHostsFile(os.path.join(os.path.dirname(__file__),
                                             'hosts_file.txt'))
        all_etc_hosts = sorted(hf.iter_all_host_addr_pairs())
        if len(all_etc_hosts) > cls.MAX_HOSTS and not DEBUG:
            all_etc_hosts = all_etc_hosts[:cls.MAX_HOSTS]

        for host, ip in all_etc_hosts:
            add(cls, host)
            add(cls, ip)



TestEtcHosts.populate_tests()



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

    def test_inet(self):
        self.assertEqualResults(self.getresult(),
                                gevent_socket.getaddrinfo(TestGeventOrg.HOSTNAME, None, socket.AF_INET),
                                'getaddrinfo')

    def test_unspec(self):
        self.assertEqualResults(self.getresult(),
                                gevent_socket.getaddrinfo(TestGeventOrg.HOSTNAME, None, socket.AF_UNSPEC),
                                'getaddrinfo')

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

    @unittest.skipIf(RESOLVER_DNSPYTHON,
                     "dnspython only returns some of the possibilities")
    def test3(self):
        return self._test_getaddrinfo('google.com', 'http', socket.AF_INET6)


    @greentest.skipIf(PY2, "Enums only on Python 3.4+")
    def test_enums(self):
        # https://github.com/gevent/gevent/issues/1310

        # On Python 3, getaddrinfo does special things to make sure that
        # the fancy enums are returned.

        gai = gevent_socket.getaddrinfo('example.com', 80,
                                        socket.AF_INET,
                                        socket.SOCK_STREAM, socket.IPPROTO_TCP)
        af, socktype, _proto, _canonname, _sa = gai[0]
        self.assertIs(socktype, socket.SOCK_STREAM)
        self.assertIs(af, socket.AF_INET)

class TestInternational(TestCase):
    pass

# dns python can actually resolve these: it uses
# the 2008 version of idna encoding, whereas on Python 2,
# with the default resolver, it tries to encode to ascii and
# raises a UnicodeEncodeError. So we get different results.
add(TestInternational, u'президент.рф', 'russian',
    skip=(PY2 and RESOLVER_DNSPYTHON), skip_reason="dnspython can actually resolve these")
add(TestInternational, u'президент.рф'.encode('idna'), 'idna')


class TestInterrupted_gethostbyname(gevent.testing.timing.AbstractGenericWaitTestCase):

    # There are refs to a Waiter in the C code that don't go
    # away yet; one gc may or may not do it.
    @greentest.ignores_leakcheck
    def test_returns_none_after_timeout(self):
        super(TestInterrupted_gethostbyname, self).test_returns_none_after_timeout()

    def wait(self, timeout):
        with gevent.Timeout(timeout, False):
            for index in xrange(1000000):
                try:
                    gevent_socket.gethostbyname('www.x%s.com' % index)
                except socket.error:
                    pass
            raise AssertionError('Timeout was not raised')

    def cleanup(self):
        # Depending on timing, this can raise:
        # (This suddenly started happening on Apr 6 2016; www.x1000000.com
        # is apparently no longer around)

        #    File "test__socket_dns.py", line 538, in cleanup
        #     gevent.get_hub().threadpool.join()
        #   File "/home/travis/build/gevent/gevent/src/gevent/threadpool.py", line 108, in join
        #     sleep(delay)
        #   File "/home/travis/build/gevent/gevent/src/gevent/hub.py", line 169, in sleep
        #     hub.wait(loop.timer(seconds, ref=ref))
        #   File "/home/travis/build/gevent/gevent/src/gevent/hub.py", line 651, in wait
        #     result = waiter.get()
        #   File "/home/travis/build/gevent/gevent/src/gevent/hub.py", line 899, in get
        #     return self.hub.switch()
        #   File "/home/travis/build/gevent/gevent/src/greentest/greentest.py", line 520, in switch
        #     return _original_Hub.switch(self, *args)
        #   File "/home/travis/build/gevent/gevent/src/gevent/hub.py", line 630, in switch
        #     return RawGreenlet.switch(self)
        # gaierror: [Errno -2] Name or service not known
        try:
            gevent.get_hub().threadpool.join()
        except Exception: # pragma: no cover pylint:disable=broad-except
            traceback.print_exc()


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


@greentest.skipIf(greentest.RUNNING_ON_TRAVIS, "Travis began returning ip6-localhost")
class Test_getnameinfo_127001(TestCase):

    def test(self):
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
        self._test('getnameinfo', ('localhost', 80), 55555555)


class TestInvalidPort(TestCase):

    def test1(self):
        self._test('getnameinfo', ('www.gevent.org', -1), 0)

    def test2(self):
        self._test('getnameinfo', ('www.gevent.org', None), 0)

    def test3(self):
        self._test('getnameinfo', ('www.gevent.org', 'x'), 0)

    @unittest.skipIf(RESOLVER_DNSPYTHON,
                     "System resolvers do funny things with this: macOS raises gaierror, "
                     "Travis CI returns (readthedocs.org, '0'). It's hard to match that exactly. "
                     "dnspython raises OverflowError.")
    def test4(self):
        self._test('getnameinfo', ('www.gevent.org', 65536), 0)


if __name__ == '__main__':
    greentest.main()
