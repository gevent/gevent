import greentest
import gevent
from gevent import pywsgi
import test__server
from test__server import *
from test__server import Settings as server_Settings


def application(self, environ, start_response):
    if environ['PATH_INFO'] == '/':
        start_response("200 OK", [])
        return [b"PONG"]
    if environ['PATH_INFO'] == '/ping':
        start_response("200 OK", [])
        return [b"PONG"]
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


internal_error_start = b'HTTP/1.1 500 Internal Server Error\n'.replace(b'\n', b'\r\n')
internal_error_end = b'\n\nInternal Server Error'.replace(b'\n', b'\r\n')

internal_error503 = b'''HTTP/1.1 503 Service Unavailable
Connection: close
Content-type: text/plain
Content-length: 31

Service Temporarily Unavailable'''.replace(b'\n', b'\r\n')


class Settings:
    ServerClass = pywsgi.WSGIServer
    ServerSubClass = SimpleWSGIServer
    close_socket_detected = True
    restartable = False
    close_socket_detected = False

    @staticmethod
    def assert500(self):
        conn = self.makefile()
        conn.write(b'GET / HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result.startswith(internal_error_start), (result, internal_error_start)
        assert result.endswith(internal_error_end), (result, internal_error_end)

    assertAcceptedConnectionError = assert500

    @staticmethod
    def assert503(self):
        conn = self.makefile()
        conn.write(b'GET / HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result == internal_error503, (result, internal_error503)

    @staticmethod
    def assertPoolFull(self):
        self.assertRaises(socket.timeout, self.assertRequestSucceeded)

    @staticmethod
    def assertAcceptedConnectionError(self):
        conn = self.makefile()
        result = conn.read()
        assert not result, repr(result)


test__server.Settings = Settings

del TestNoneSpawn

if __name__ == '__main__':
    greentest.main()
