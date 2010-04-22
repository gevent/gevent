import unittest
import gevent
from gevent import pywsgi
import test__server
from test__server import *
from test__server_http import Settings as http_Settings

import gevent.wsgi; gevent.wsgi.WSGIServer.__init__ = None


def application(self, environ, start_response):
    if environ['PATH_INFO'] == '/ping':
        start_response("200 OK", [])
        return ["PONG"]
    else:
        start_response("404 pywsgi WTF?", [])
        return []


class SimpleWSGIServer(pywsgi.WSGIServer):
    application = application


class Settings(http_Settings):
    ServerClass = pywsgi.WSGIServer
    ServerSubClass = SimpleWSGIServer


test__server.Settings = Settings

TestNoneSpawn.invalid_callback_message = 'Failed to handle...'
TestRawSpawn.invalid_callback_message = 'Failed to handle...'
TestPoolSpawn.invalid_callback_message = 'Failed to handle...'
TestDefaultSpawn.invalid_callback_message = 'Failed to handle...'

if __name__ == '__main__':
    unittest.main()

