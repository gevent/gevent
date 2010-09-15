import unittest
import gevent
from gevent import http
import test__server
from test__server import *

internal_error_start = 'HTTP/1.0 500 Internal Server Error\n'.replace('\n', '\r\n')
internal_error_end = '\n\nInternal Server Error'.replace('\n', '\r\n')

internal_error503 = '''HTTP/1.0 503 Service Unavailable
Connection: close
Content-type: text/plain
Content-length: 31

Service Temporarily Unavailable'''.replace('\n', '\r\n')


class SimpleHTTPServer(http.HTTPServer):

    def handle(self, request):
        if request.uri == '/ping':
            request.send_reply(200, "OK", "PONG")
        elif request.uri == '/short':
            gevent.sleep(0.1)
            request.send_reply(200, "OK", 'hello')
        elif request.uri == '/long':
            gevent.sleep(10)
            request.send_reply(200, "OK", 'hello')
        else:
            request.send_reply(404, "gevent.http", "")


class Settings:
    ServerClass = http.HTTPServer
    ServerSubClass = SimpleHTTPServer
    restartable = False
    close_socket_detected = False

    @staticmethod
    def assert500(self):
        conn = self.makefile()
        conn.write('GET / HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result.startswith(internal_error_start), (result, internal_error_start)
        assert result.endswith(internal_error_end), (result, internal_error_end)

    assertAcceptedConnectionError = assert500

    @staticmethod
    def assert503(self):
        conn = self.makefile()
        conn.write('GET / HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result == internal_error503, (result, internal_error503)

    assertPoolFull = assert503


test__server.Settings = Settings


if __name__ == '__main__':
    unittest.main()
