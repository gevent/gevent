import gevent
from gevent import wsgi
import test__pywsgi
from test__pywsgi import *

del TestHttps
test__pywsgi.server_implements_chunked = False
test__pywsgi.server_implements_pipeline = False
test__pywsgi.server_implements_100continue = False
TestCase.get_wsgi_module = lambda *args: wsgi


if __name__ == '__main__':
    greentest.main()
