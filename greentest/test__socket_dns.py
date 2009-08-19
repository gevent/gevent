#!/usr/bin/python
from gevent import monkey; monkey.patch_all()
from gevent import socket

import unittest

class GetAddrInfoTest(unittest.TestCase):

    def test_localhost(self):
        socket.getaddrinfo('localhost', 0)
        socket.getaddrinfo('127.0.0.1', 0)

    def test_google(self):
        socket.getaddrinfo('www.google.com', 80)

class GetNameInfoTest(unittest.TestCase):

    def test_localhost(self):
        socket.getnameinfo(('127.0.0.1', 0), 0)

    def test_google(self):
        socket.getnameinfo(('74.125.19.105', 80), 0)

class GetHostByNameTest(unittest.TestCase):

    def test_localhost(self):
        socket.gethostbyname('localhost')
        socket.gethostbyname('127.0.0.1')

    def test_google(self):
        socket.gethostbyname('www.google.com')

if __name__ == "__main__":
    unittest.main()

