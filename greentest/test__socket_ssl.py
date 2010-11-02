#!/usr/bin/python
from gevent import monkey; monkey.patch_all()
import sys
import unittest
import httplib
import socket

if not hasattr(socket, 'ssl'):
    sys.exit(0)


class AmazonHTTPSTests(unittest.TestCase):

    def test_amazon_response(self):
        conn = httplib.HTTPSConnection('sdb.amazonaws.com')
        conn.debuglevel = 1
        conn.request('GET', '/')
        conn.getresponse()

    def test_str_and_repr(self):
        conn = socket.socket()
        conn.connect(('sdb.amazonaws.com', 443))
        ssl_conn = socket.ssl(conn)
        assert str(ssl_conn)
        assert repr(ssl_conn)


if __name__ == "__main__":
    unittest.main()
