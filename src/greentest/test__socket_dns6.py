#!/usr/bin/python
# -*- coding: utf-8 -*-
import greentest
import socket
from test__socket_dns import TestCase, add, RESOLVER_IS_ARES


class Test6(TestCase):

    # host that only has AAAA record
    host = 'aaaa.test-ipv6.com'

    def test_empty(self):
        self._test('getaddrinfo', self.host, 'http')

    def test_inet(self):
        self._test('getaddrinfo', self.host, None, socket.AF_INET)

    def test_inet6(self):
        self._test('getaddrinfo', self.host, None, socket.AF_INET6)

    def test_unspec(self):
        self._test('getaddrinfo', self.host, None, socket.AF_UNSPEC)


class Test6_google(Test6):
    host = 'ipv6.google.com'

    def _normalize_result_getnameinfo(self, result):
        if greentest.RUNNING_ON_CI and RESOLVER_IS_ARES:
            # Disabled, there are multiple possibilities
            # and we can get different ones, rarely.
            return ()
        return result

add(Test6, Test6.host)
add(Test6_google, Test6_google.host)


if not greentest.RUNNING_ON_CI:
    # We can't control the DNS servers we use there
    # for the system. This works best with the google DNS servers
    # The getnameinfo test can fail on CI
    class Test6_ds(Test6):
        # host that has both A and AAAA records
        host = 'ds.test-ipv6.com'

        def _normalize_result_gethostbyaddr(self, result):
            # This test is effectively disabled. There are multiple address
            # that resolve and which ones you get depend on the settings
            # of the system and ares. They don't match exactly.
            return ()

        _normalize_result_gethostbyname = _normalize_result_gethostbyaddr

    add(Test6_ds, Test6_ds.host)


if __name__ == '__main__':
    greentest.main()
