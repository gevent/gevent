#!/usr/bin/python
import greentest
from gevent import dns
from gevent import core
from gevent.dns import DNSError

funcs = [dns.resolve_ipv4, dns.resolve_ipv6,
         dns.resolve_reverse, dns.resolve_reverse_ipv6]


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
    __timeout__ = 10

    def test_empty_string(self):
        self.assertRaises(DNSError, dns.resolve_ipv4, '')
        self.assertRaises(DNSError, dns.resolve_ipv6, '')
        self.assertRaises(DNSError, dns.resolve_reverse, '')
        self.assertRaises(DNSError, dns.resolve_reverse_ipv6, '')


if __name__ == '__main__':
    greentest.main()
