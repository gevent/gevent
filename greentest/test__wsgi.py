from gevent import wsgi
import wsgi_test
from wsgi_test import *

del TestHttps
wsgi_test.server_implements_chunked = False
TestCase.get_wsgi_module = lambda *args: wsgi


class TestHttpsError(HttpsTestCase):

    def setUp(self):
        listener = self.get_listener()
        self.assertRaises(TypeError, self.get_wsgi_module().WSGIServer, listener, self.application)

    def tearDown(self):
        pass

    def test(self):
        pass

  
if __name__ == '__main__':
    greentest.main()
