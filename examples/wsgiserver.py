"""This is a simple example of running a wsgi application with gevent.
For a more fully-featured server which supports multiple processes,
multiple threads, and graceful code reloading, see:

http://pypi.python.org/pypi/Spawning/
"""
from gevent import wsgi, socket

def hello_world(env, start_response):
    if env['PATH_INFO'] != '/':
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return ['Not Found\r\n']
    else:
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ["Hello World!\r\n"]

wsgi.server(socket.tcp_listener(('', 8080)), hello_world)

