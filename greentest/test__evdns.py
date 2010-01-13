#!/usr/bin/python
import greentest
from gevent import evdns
from gevent import core
from gevent import socket

funcs = [evdns.resolve_ipv4, evdns.resolve_ipv6,
         evdns.resolve_reverse, evdns.resolve_reverse_ipv6]


class TestNoSwitch(greentest.TestCase):

    switch_expected = False

    def test_type_error(self):
        for func in funcs:
            self.assertRaises(TypeError, func, None)
            self.assertRaises(TypeError, func, 15)
            self.assertRaises(TypeError, func, object())

    def test_dns_err_to_string(self):
        for err in range(-100, 100):
            result = core.dns_err_to_string(err)
            assert result, result
            assert isinstance(result, str)


class TestSwitch(greentest.TestCase):

    switch_expected = True

    def test_empty_string(self):
        self.assertRaises(evdns.DNSError, evdns.resolve_ipv4, '')
        self.assertRaises(evdns.DNSError, evdns.resolve_ipv6, '')
        self.assertRaises(evdns.DNSError, evdns.resolve_reverse, '')
        self.assertRaises(evdns.DNSError, evdns.resolve_reverse_ipv6, '')


if __name__ == '__main__':
    greentest.main()

