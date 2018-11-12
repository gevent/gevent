#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import, division

import gevent.testing as greentest
import socket
from gevent.tests.test__socket_dns import TestCase, add

from gevent.testing.sysinfo import RESOLVER_NOT_SYSTEM
from gevent.testing.sysinfo import RESOLVER_DNSPYTHON

if not greentest.RUNNING_ON_CI and not RESOLVER_DNSPYTHON:


    # We can't control the DNS servers we use there
    # for the system. This works best with the google DNS servers
    # The getnameinfo test can fail on CI.

    # Previously only Test6_ds failed, but as of Jan 2018, Test6
    # and Test6_google begin to fail:

      # First differing element 0:
    # 'vm2.test-ipv6.com'
    # 'ip119.gigo.com'

    # - ('vm2.test-ipv6.com', [], ['2001:470:1:18::125'])
    # ?   ---------  ^^                             ^^

    # + ('ip119.gigo.com', [], ['2001:470:1:18::119'])
    # ?     ^^^^^^^^                             ^^

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
            if greentest.RUNNING_ON_CI and RESOLVER_NOT_SYSTEM:
                # Disabled, there are multiple possibilities
                # and we can get different ones, rarely.
                return ()
            return result

    add(Test6, Test6.host)
    add(Test6_google, Test6_google.host)



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
