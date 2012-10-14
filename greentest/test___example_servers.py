import sys
import time
from unittest import main
if sys.version_info[0] == 3:
    from urllib import request as urllib2
else:
    import urllib2

import util


class Test_wsgiserver(util.TestServer):
    server = 'wsgiserver.py'
    URL = 'http://127.0.0.1:8088'
    not_found_message = '<h1>Not Found</h1>'

    def read(self, path='/'):
        url = self.URL + path
        try:
            response = urllib2.urlopen(url)
        except urllib2.HTTPError:
            response = sys.exc_info()[1]
        return '%s %s' % (response.code, response.msg), response.read()

    def _test_hello(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        self.assertEqual(data, "<b>hello world</b>")

    def _test_not_found(self):
        status, data = self.read('/xxx')
        self.assertEqual(status, '404 Not Found')
        self.assertEqual(data, self.not_found_message)


class Test_wsgiserver_ssl(Test_wsgiserver):
    server = 'wsgiserver_ssl.py'
    URL = 'https://127.0.0.1:8443'


class Test_webproxy(Test_wsgiserver):
    server = 'webproxy.py'

    def _run_all_tests(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        assert "gevent example" in data, repr(data)
        status, data = self.read('/http://www.google.com')
        self.assertEqual(status, '200 OK')
        assert 'google' in data.lower(), repr(data)


class Test_webpy(Test_wsgiserver):
    server = 'webpy.py'
    not_found_message = 'not found'

    def _test_hello(self):
        status, data = self.read('/')
        self.assertEqual(status, '200 OK')
        assert "Hello, world" in data, repr(data)

    def _test_long(self):
        start = time.time()
        status, data = self.read('/long')
        delay = time.time() - start
        assert 10 - 0.5 < delay < 10 + 0.5, delay
        self.assertEqual(status, '200 OK')
        self.assertEqual(data, 'Hello, 10 seconds later')


if __name__ == '__main__':
    main()
