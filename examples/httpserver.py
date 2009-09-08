"""HTTP server listening on port 8800.

Uses libevent API directly and thus may be dangerous.
WSGI interface is probably a safer choice, see examples/wsgiserver.py.
"""
from gevent import http

def callback(r):
    if r.uri == '/':
        r.add_output_header('Content-Type', 'text/html')
        r.send_reply(200, "OK", '<b>hello world</b>')
    else:
        r.add_output_header('Content-Type', 'text/html')
        r.send_reply(404, "Not Found", "<h1>Not Found</h1>")

print __doc__
http.HTTPServer(callback).serve_forever(('0.0.0.0', 8800))
