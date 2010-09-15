import unittest
import gevent
from gevent import pywsgi
import test__server
from test__server import *
from test__server import Settings as server_Settings
from test__server_http import Settings as http_Settings

import gevent.wsgi; gevent.wsgi.WSGIServer.__init__ = None


def application(self, environ, start_response):
    if environ['PATH_INFO'] == '/':
        start_response("200 OK", [])
        return ["PONG"]
    if environ['PATH_INFO'] == '/ping':
        start_response("200 OK", [])
        return ["PONG"]
    elif environ['PATH_INFO'] == '/short':
        gevent.sleep(0.5)
        start_response("200 OK", [])
        return []
    elif environ['PATH_INFO'] == '/long':
        gevent.sleep(10)
        start_response("200 OK", [])
        return []
    else:
        start_response("404 pywsgi WTF?", [])
        return []


class SimpleWSGIServer(pywsgi.WSGIServer):
    application = application


class Settings(http_Settings):
    ServerClass = pywsgi.WSGIServer
    ServerSubClass = SimpleWSGIServer
    close_socket_detected = True

    @staticmethod
    def assertPoolFull(self):
        self.assertRaises(socket.timeout, self.assertRequestSucceeded)

    @staticmethod
    def assertAcceptedConnectionError(self):
        conn = self.makefile()
        result = conn.read()
        assert not result, repr(result)


test__server.Settings = Settings

msg = '<.*?>: Failed to handle...'

TestNoneSpawn.invalid_callback_message = msg
TestRawSpawn.invalid_callback_message = msg
TestPoolSpawn.invalid_callback_message = msg
TestDefaultSpawn.invalid_callback_message = msg

del TestNoneSpawn

if __name__ == '__main__':
    unittest.main()
