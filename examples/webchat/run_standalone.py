#!/usr/bin/python
from __future__ import print_function
from gevent.wsgi import WSGIServer
from application import application
print('Serving on 8000...')
WSGIServer(('', 8000), application).serve_forever()
