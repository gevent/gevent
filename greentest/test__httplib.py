import unittest
from gevent import httplib


class Test(unittest.TestCase):

    def test(self):
        conn = httplib.HTTPConnection('www.google.com')
        conn.request('GET', '/')
        conn.getresponse()


if __name__ == "__main__":
    unittest.main()
