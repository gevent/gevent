#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import re
import traceback
import greentest
import socket as real_socket
import gevent
from gevent.socket import gethostbyname, getaddrinfo, AF_INET, AF_INET6, AF_UNSPEC, SOCK_DGRAM, SOCK_STREAM, gaierror, error


ACCEPTED_GAIERROR_MISMATCH = {
    # EAI_NODATA (-5) is deprecated in RFC3493, so libevent's resolves returning -2 is also right here
    "gaierror(-5, 'No address associated with hostname')": "gaierror(-2, 'Name or service not known')"}

assert gaierror is real_socket.gaierror
assert error is real_socket.error

VERBOSE = sys.argv.count('-v') >= 2 or '-vv' in sys.argv
PASS = True

if VERBOSE:

    def log(s, *args):
        try:
            s = s % args
        except Exception:
            traceback.print_exc()
            s = '%s %r' % (s, args)
        sys.stdout.write(s + '\n')
else:

    def log(*args):
        pass


class TestCase(greentest.TestCase):

    def _test(self, hostname, check_ip=None, fail=False):
        self._test_gethostbyname(hostname, check_ip=check_ip)
        self._test_getaddrinfo(hostname, 80, 0, SOCK_STREAM, fail=fail)

    def _test_gethostbyname(self, hostname, check_ip=None):
        log('\nreal_socket.gethostbyname(%r)', hostname)
        try:
            real_ip = real_socket.gethostbyname(hostname)
            log('    returned %r', real_ip)
        except Exception, ex:
            real_ip = ex
            log('    raised %r', real_ip)
        try:
            log('gevent.socket.gethostbyname(%r)', hostname)
            ip = gethostbyname(hostname)
            log('    returned %r', ip)
        except Exception, ex:
            ip = ex
            log('    raised %r', ip)
        if self.equal(real_ip, ip):
            return ip
        self.assertEqual(real_ip, ip)
        if check_ip is not None:
            self.assertEqual(check_ip, ip)
        return ip

    def _test_getaddrinfo(self, *args, **kwargs):
        fail = kwargs.get('fail', False)
        has_failed = None
        log('\nreal_socket.getaddrinfo%r', args)
        try:
            real_ip = real_socket.getaddrinfo(*args)
            log('    returned %r', real_ip)
        except Exception, ex:
            real_ip = ex
            log('    raised %r', real_ip)
            has_failed = True
        log('gevent.socket.getaddrinfo%r', args)
        try:
            ip = getaddrinfo(*args)
            log('    returned %r', ip)
        except Exception, ex:
            ip = ex
            log('    raised %r', ex)
            has_failed = True
        if not self.equal(real_ip, ip):
            args_str = ', '.join(repr(x) for x in args)
            msg = 'getaddrinfo(%s):\n expected: %r\n      got: %r' % (args_str, real_ip, ip)
            if PASS:
                log(msg)
            else:
                raise AssertionError(msg)
        if fail is None:
            pass
        elif fail:
            if not has_failed:
                raise AssertionError('getaddinfo must fail')
        else:
            if has_failed:
                raise AssertionError('getaddrinfo failed')

    def equal(self, a, b):
        if a == b:
            return True
        if isinstance(a, list) and isinstance(b, list) and sorted(a) == sorted(b):
            return True
        if isinstance(a, Exception) and isinstance(b, Exception):
            if repr(a) == repr(b):
                return True
            if ACCEPTED_GAIERROR_MISMATCH.get(repr(a), repr(b)) == repr(b):
                return True

    def checkEqual(self, a, b):
        if a == b:
            return
        print 'WARNING: %s.%s:\n    %r\n != %r' % (self.__class__.__name__, self.testname, a, b)


def get_test(ip, host):

    def test(self):
        self._test(host, check_ip=ip)
    test.__name__ = 'test_' + re.sub('[^\w]', '_', host + '__' + ip)

    return test


class TestLocal(TestCase):

    switch_expected = False

    def test_hostname(self):
        hostname = real_socket.gethostname()
        self._test(hostname)

    def test_localhost(self):
        self._test('localhost')

    def test_127_0_0_1(self):
        self._test('127.0.0.1')

    def test_1_2_3_4(self):
        self._test('1.2.3.4')

    def test_notexistent(self):
        # not really interesting because the original gethostbyname() is called for everything without dots
        # disabled because it takes too much time on windows for some reason
        self.switch_expected = True
        self._test('notexistent', fail=True)

    def test_None(self):
        self._test(None)

    def test_25(self):
        self._test(25, fail=True)

    try:
        etc_hosts = open('/etc/hosts').read()
    except IOError:
        etc_hosts = ''

    for ip, host in re.findall(r'^\s*(\d+\.\d+\.\d+\.\d+)\s+([^\s]+)', etc_hosts, re.M)[:10]:
        func = get_test(ip, host)
        #print 'Adding %s' % func.__name__
        locals()[func.__name__] = func
        del func


class TestGethostbyname(TestCase):

    def test(self):
        self._test_gethostbyname('gevent.org')


class TestGetaddrinfo(TestCase):

    switch_expected = True

    def test_80(self):
        self._test_getaddrinfo('gevent.org', 80)

    def test_0(self):
        self._test_getaddrinfo('gevent.org', 0)

    def test_http(self):
        self._test_getaddrinfo('gevent.org', 'http')

    def test_notexistent_tld(self):
        self._test_getaddrinfo('myhost.mytld', fail=True)

    def test_notexistent_dot_com(self):
        self._test_getaddrinfo('sdfsdfgu5e66098032453245wfdggd.com', fail=True)

    def test1(self):
        return self._test_getaddrinfo('gevent.org', 52, AF_UNSPEC, SOCK_STREAM, 0, 0)

    def test2(self):
        return self._test_getaddrinfo('gevent.org', 53, AF_INET, SOCK_DGRAM, 17)

    def test3(self):
        return self._test_getaddrinfo('google.com', 'http', AF_INET6, fail=None)


class TestInternational(TestCase):

    def test_getaddrinfo(self):
        self._test_getaddrinfo(u'президент.рф', 80)

    def test_gethostbyname(self):
        self.switch_expected = False
        self._test_gethostbyname(u'президент.рф')


class TestInterrupted(greentest.GenericWaitTestCase):

    def wait(self, timeout):
        with gevent.Timeout(timeout, False):
            return getaddrinfo('www.gevent.org', 'http')


if __name__ == '__main__':
    greentest.main()
