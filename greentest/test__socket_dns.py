#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import re
import greentest
import socket as real_socket
from gevent.socket import *


ACCEPTED_GAIERROR_MISMATCH = {
    "gaierror(-5, 'No address associated with hostname')":
    ("DNSError(3, 'name does not exist')", "DNSError(66, 'unknown')"),
}

assert gaierror is real_socket.gaierror
assert error is real_socket.error

VERBOSE = '-v' in sys.argv
IGNORE_ERRORS = '--ignore' in sys.argv
DEBUG = '-d' in sys.argv
for arg in ['--ignore', '-d']:
    try:
        sys.argv.remove(arg)
    except ValueError:
        pass


class TestCase(greentest.TestCase):
    __timeout__ = 30

    if IGNORE_ERRORS:
        def assertEqual(self, a, b):
            if a != b:
                print 'ERROR: %r != %r' % (a, b)

    def _test(self, hostname, check_ip=None):
        self._test_gethostbyname(hostname, check_ip=check_ip)
        self._test_getaddrinfo(hostname)

    def _test_gethostbyname(self, hostname, check_ip=None):
        try:
            if VERBOSE:
                print 'real_socket.gethostbyname(%r)' % (hostname, )
            real_ip = real_socket.gethostbyname(hostname)
        except Exception, ex:
            if DEBUG:
                raise
            real_ip = ex
        try:
            if VERBOSE:
                print 'gevent.socket.gethostbyname(%r)' % (hostname, )
            ip = gethostbyname(hostname)
        except Exception, ex:
            if DEBUG:
                raise
            ip = ex
        if self.equal(real_ip, ip):
            return ip
        self.assertEqual(real_ip, ip)
        if check_ip is not None:
            self.assertEqual(check_ip, ip)
        return ip

    PORTS = [80, 0, 53, 'http']
    getaddrinfo_args = [(),
                        (AF_UNSPEC, ),
                        (AF_UNSPEC, SOCK_STREAM, 0, 0),
                        (AF_INET, SOCK_STREAM, ),
                        (AF_UNSPEC, SOCK_DGRAM, ),
                        (AF_INET, SOCK_RAW, ),
                        (AF_UNSPEC, SOCK_STREAM, 6),
                        (AF_INET, SOCK_DGRAM, 17)]

    def _test_getaddrinfo(self, hostname):
        for port in self.PORTS:
            for args in self.getaddrinfo_args:
                if VERBOSE:
                    print
                    print 'real_socket.getaddrinfo(%r, %r, %r)' % (hostname, port, args)
                try:
                    real_ip = real_socket.getaddrinfo(hostname, port, *args)
                    if VERBOSE:
                        print '    returned %r' % (real_ip, )
                except Exception, ex:
                    if DEBUG:
                        raise
                    real_ip = ex
                if VERBOSE:
                    print 'gevent.socket.getaddrinfo(%r, %r, %r)' % (hostname, port, args)
                try:
                    ip = getaddrinfo(hostname, port, *args)
                    if VERBOSE:
                        print '    returned %r' % (ip, )
                except Exception, ex:
                    if DEBUG:
                        raise
                    ip = ex
                if not self.equal(real_ip, ip):
                    args_str = ', '.join(repr(x) for x in (hostname, port) + args)
                    print 'WARNING: getaddrinfo(%s):\n    %r    (stdlib)\n != %r    (gevent)' % (args_str, real_ip, ip)
        # QQQ switch_expected becomes useless when a bunch of unrelated tests are merged
        #     into a single one like above. Generate individual test cases instead?

    def equal(self, a, b):
        if a == b:
            return True
        if isinstance(a, Exception) and isinstance(b, Exception):
            if repr(a) == repr(b):
                return True
            if repr(b) in ACCEPTED_GAIERROR_MISMATCH.get(repr(a), (repr(b), )):
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

    def SKIP_test_notexistent(self):
        # not really interesting because the original gethostbyname() is called for everything without dots
        # disabled because it takes too much time on windows for some reason
        self._test('notexistent')

    def test_None(self):
        self._test(None)

    def test_25(self):
        self._test(25)

    try:
        etc_hosts = open('/etc/hosts').read()
    except IOError:
        etc_hosts = ''

    for ip, host in re.findall(r'^\s*(\d+\.\d+\.\d+\.\d+)\s+([^\s]+)', etc_hosts, re.M)[:10]:
        func = get_test(ip, host)
        print 'Adding %s' % func.__name__
        locals()[func.__name__] = func
        del func


class TestRemote(TestCase):

    switch_expected = True

    def test_www_python_org(self):
        self._test('www.python.org')

    def test_notexistent_tld(self):
        self._test('myhost.mytld')

    def test_notexistent_dot_com(self):
        self._test('sdfsdfgu5e66098032453245wfdggd.com')


class TestInternational(TestCase):

    def test(self):
        self._test(u'президент.рф')


class TestIPv6(TestCase):

    def test(self):
        #self.PORTS = ['http']
        #self.getaddrinfo_args = [(), (AF_UNSPEC, ), (AF_INET, ), (AF_INET6, )]
        self._test('aaaa.test-ipv6.com')


class TestBadPort(TestCase):

    def test(self):
        self.PORTS = ['xxxxxx']
        self._test('www.google.com')


if __name__ == '__main__':
    greentest.main()
