import gevent
from gevent import wsgi
import test__pywsgi
from test__pywsgi import *

del TestHttps
test__pywsgi.server_implements_chunked = False
test__pywsgi.server_supports_pipeline = gevent.core.get_version()[1] == '2'
TestCase.get_wsgi_module = lambda *args: wsgi


class TestHttpsError(HttpsTestCase):

    def setUp(self):
        from gevent.socket import ssl, socket
        listener = socket()
        listener.bind(('0.0.0.0', 0))
        listener.listen(5)
        listener = ssl(listener, keyfile=self.keyfile, certfile=self.certfile)
        self.assertRaises(TypeError, self.get_wsgi_module().WSGIServer, listener, self.application)

    def tearDown(self):
        pass

    def test(self):
        pass

  
if __name__ == '__main__':
    greentest.main()
