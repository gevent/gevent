from gevent import wsgi
import wsgi_test
from wsgi_test import *

del TestHttps
wsgi_test.server_implements_chunked = False
TestCase.get_wsgi_module = lambda *args: wsgi


if __name__ == '__main__':
    greentest.main()
