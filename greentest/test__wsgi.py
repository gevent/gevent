import sys
from gevent import wsgi
from wsgi_test import *

del TestHttps, TestChunkedApp, TestBigChunks

TestCase.get_wsgi_module = lambda *args: wsgi

class Expected(Exception):
    pass

class TestError(TestCase):

    @staticmethod
    def application(env, start_response):
        raise Expected

    @property
    def url(self):
        return 'http://127.0.0.1:%s' % self.port

    def test(self):
        try:
            r = urllib2.urlopen(self.url)
            raise AssertionError('Must raise HTTPError, returned %r: %s' % (r, r.code))
        except urllib2.HTTPError, ex:
            assert ex.code == 500, ex
            assert ex.msg == 'Internal Server Error', ex


class TestError_after_start_response(TestError):

    @staticmethod
    def application(env, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        raise Expected


if __name__ == '__main__':
    greentest.main()
