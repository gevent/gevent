import unittest
import gevent
from gevent import http
import test__server
from test__server import *

internal_error = '''HTTP/1.0 500 Internal Server Error
Connection: close
Content-type: text/plain
Content-length: 21

Internal Server Error'''.replace('\n', '\r\n')


internal_error503 = '''HTTP/1.0 503 Service Unavailable
Connection: close
Content-type: text/plain
Content-length: 31

Service Temporarily Unavailable'''.replace('\n', '\r\n')

class SimpleHTTPServer(http.HTTPServer):

    def handle(self, request):
        if request.uri == '/ping':
            request.send_reply(200, "OK", "PONG")
        elif request.uri == '/long':
            request.send_reply_start(200, "OK")
            request.send_reply_chunk("hello")
            while request:
                print request
                gevent.sleep(0.01)
        else:
            request.send_reply(404, "what?", "")


class Settings:
    ServerClass = http.HTTPServer
    ServerSubClass = SimpleHTTPServer
    restartable = False

    @staticmethod
    def assert500(self):
        conn = self.makefile()
        conn.write('GET / HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result == internal_error, (result, internal_error)

    @staticmethod
    def assert503(self):
        conn = self.makefile()
        conn.write('GET / HTTP/1.0\r\n\r\n')
        result = conn.read()
        assert result == internal_error503, (result, internal_error503)


test__server.Settings = Settings


if __name__ == '__main__':
    unittest.main()

