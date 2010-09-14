#!/usr/bin/python
"""HTTP server example.

Uses libevent API directly and thus may be dangerous.
WSGI interface is a safer choice, see examples/wsgiserver.py.
"""
from gevent import http


def callback(request):
    print request
    if request.uri == '/':
        request.add_output_header('Content-Type', 'text/html')
        request.send_reply(200, "OK", '<b>hello world</b>')
    else:
        request.add_output_header('Content-Type', 'text/html')
        request.send_reply(404, "Not Found", "<h1>Not Found</h1>")

print 'Serving on 8088...'
http.HTTPServer(('0.0.0.0', 8088), callback).serve_forever()
