#/usr/bin/python
"""Simple wsgi app. Serving on 8088.
"""

from gevent import wsgi2

def hello_world(env, start_response):
    if env['PATH_INFO'] == '/':
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return ["Hello World!\r\n"]
    else:
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return ['Not Found\r\n']

print __doc__
wsgi2.WSGIServer(('', 8088), hello_world).serve_forever()

