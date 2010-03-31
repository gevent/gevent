import sys
from gevent import wsgi
from wsgi_test import *

del TestHttps, TestChunkedApp, TestBigChunks

TestCase.get_wsgi_module = lambda *args: wsgi


if __name__ == '__main__':
    greentest.main()
