from __future__ import print_function

import errno
import unittest

import gevent
try:
    from gevent.resolver.ares import Resolver
except ImportError as ex:
    Resolver = None
from gevent import socket

import gevent.testing as greentest

@unittest.skipIf(
    Resolver is None,
    "Needs ares resolver"
)
class TestTimeout(greentest.TestCase):

    __timeout__ = 30

    address = ('', 7153)

    def test(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            listener.bind(self.address)
        except socket.error as ex:
            if ex.errno in (errno.EPERM, errno.EADDRNOTAVAIL) or 'permission denied' in str(ex).lower():
                raise unittest.SkipTest(
                    'This test binds on port a port that was already in use or not allowed.\n'
                )
            raise


        def reader():
            while True:
                listener.recvfrom(10000)

        gevent.spawn(reader)

        r = Resolver(servers=['127.0.0.1'], timeout=0.001, tries=1,
                     udp_port=self.address[-1])

        with self.assertRaisesRegex(socket.gaierror, "ARES_ETIMEOUT"):
            r.gethostbyname('www.google.com')


if __name__ == '__main__':
    greentest.main()
