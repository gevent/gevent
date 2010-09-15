import unittest
import gevent
from gevent import wsgi
import test__server
from test__server import *
from test__server_http import Settings as http_Settings

import gevent.pywsgi; gevent.pywsgi.WSGIServer.__init__ = None


def application(self, environ, start_response):
    if environ['PATH_INFO'] == '/ping':
        start_response("200 OK", [])
        return ["PONG"]
    elif environ['PATH_INFO'] == '/short':
        gevent.sleep(0.1)
        start_response("200 after 0.1 seconds", [])
        return ["hello"]
    elif environ['PATH_INFO'] == '/long':
        gevent.sleep(10)
        start_response("200 after 10 seconds", [])
        return ["hello"]
    else:
        start_response("404 wsgi WTF?", [])
        return []


class SimpleWSGIServer(wsgi.WSGIServer):
    application = application


class Settings(http_Settings):
    ServerClass = wsgi.WSGIServer
    ServerSubClass = SimpleWSGIServer


test__server.Settings = Settings

msg = '<.*?>: Failed to handle...'

TestNoneSpawn.invalid_callback_message = msg
TestRawSpawn.invalid_callback_message = msg
TestPoolSpawn.invalid_callback_message = msg
TestDefaultSpawn.invalid_callback_message = msg

if __name__ == '__main__':
    unittest.main()
