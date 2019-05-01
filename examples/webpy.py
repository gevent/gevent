#!/usr/bin/python
# gevent-test-requires-resource: webpy
"""A web.py application powered by gevent"""

from __future__ import print_function
from gevent import monkey; monkey.patch_all()
from gevent.pywsgi import WSGIServer
import time
import web # pylint:disable=import-error

urls = ("/", "index",
        '/long', 'long_polling')


class index(object):
    def GET(self):
        return '<html>Hello, world!<br><a href="/long">/long</a></html>'


class long_polling(object):
    # Since gevent's WSGIServer executes each incoming connection in a separate greenlet
    # long running requests such as this one don't block one another;
    # and thanks to "monkey.patch_all()" statement at the top, thread-local storage used by web.ctx
    # becomes greenlet-local storage thus making requests isolated as they should be.
    def GET(self):
        print('GET /long')
        time.sleep(10)  # possible to block the request indefinitely, without harming others
        return 'Hello, 10 seconds later'


if __name__ == "__main__":
    application = web.application(urls, globals()).wsgifunc()
    print('Serving on 8088...')
    WSGIServer(('', 8088), application).serve_forever()
