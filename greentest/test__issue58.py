import sys
import gevent
from gevent import wsgi
from gevent import socket


def error(env, start_response):
    try:
        raise ValueError('hello')
    except Exception:
        exc = sys.exc_info()
        raise

server = wsgi.WSGIServer(('', 0), error)
server.start()
conn = socket.create_connection(('127.0.0.1', server.server_port))
conn.sendall('GET / HTTP/1.1\r\nConnection: close\r\n\r\n')
timeout = gevent.Timeout.start_new(0.1)
try:
    conn.makefile(bufsize=1).read()
finally:
    timeout.cancel()
