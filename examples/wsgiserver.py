#!/usr/bin/python
"""WSGI server example"""

from gevent import wsgi


def hello_world(env, start_response):
    if env['PATH_INFO'] == '/':
        start_response('200 OK', [('Content-Type', 'text/html')])
        return ["<b>hello world</b>"]
    else:
        start_response('404 Not Found', [('Content-Type', 'text/html')])
        return ['<h1>Not Found</h1>']

print 'Serving on 8088...'
wsgi.WSGIServer(('', 8088), hello_world).serve_forever()
