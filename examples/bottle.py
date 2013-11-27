#!/usr/bin/python
"""A bottle application powered by gevent"""

from gevent import monkey; monkey.patch_all()
import time
from bottle import route, run


@route('/')
def index():
    return '<html>Hello, world!<br><a href="/long">/long</a></html>'


@route('/long')
def long_polling():
    # Since bottle's gevent server adapter executes each incoming connection in a separate greenlet
    # long running requests such as this one don't block one another
    print('GET /long')
    time.sleep(10)  # possible to block the request indefinitely, without harming others
    return 'Hello, 10 seconds later'


if __name__ == "__main__":
    print('Serving on 8088...')
    run(host='0.0.0.0', port=8080, server='gevent')