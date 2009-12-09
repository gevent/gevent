#!/usr/bin/python
from gevent import monkey; monkey.patch_all()

import unittest
import httplib

class AmazonHTTPSTests(unittest.TestCase):

    def test_amazon_response(self):
        conn = httplib.HTTPConnection('sdb.amazonaws.com')
        conn.debuglevel = 1
        conn.request('GET', '/')
        resp = conn.getresponse()

if __name__ == "__main__":
    unittest.main()

