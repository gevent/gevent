
.. implementing-servers:

Implementing servers
--------------------

There are a few classes to simplify server implementation with gevent. They all share the similar interface::

  def handle(socket, address):
       print 'new connection!'

  server = StreamServer(('127.0.0.1', 1234), handle) # creates a new server
  server.start() # start accepting new connections

At this point, any new connection accepted on ``127.0.0.1:1234`` will result in a new
:class:`Greenlet` spawned using *handle* function. To stop a server use :meth:`stop` method.

In case of a :class:`WSGIServer`, handle must be a WSGI application callable.

It is possible to limit the maximum number of concurrent connections, by passing a :class:`Pool` instance::

  pool = Pool(10000) # do not accept more than 10000 connections
  server = StreamServer(('127.0.0.1', 1234), handle, spawn=pool)
  server.serve_forever()

The :meth:`server_forever` method calls :meth:`start` and then waits until interrupted or until the server is stopped.

The difference between :class:`wsgi.WSGIServer <gevent.wsgi.WSGIServer>` and :class:`pywsgi.WSGIServer <gevent.pywsgi.WSGIServer>`
is that the first one is very fast as it uses libevent's http server implementation but it shares the issues that
libevent-http has. In particular:

- `does not support streaming`_: the responses are fully buffered in memory before sending; likewise, the incoming requests are loaded in memory in full;
- `pipelining does not work`_: the server uses ``"Connection: close"`` by default;
- does not support SSL.

The :class:`pywsgi.WSGIServer <gevent.pywsgi.WSGIServer>` does not have these limitations.
In addition, gunicorn_ is a stand-alone server that supports gevent. Gunicorn has its own HTTP parser but can also use :mod:`gevent.wsgi` module.

More examples are available in the `code repository`_:

- `echoserver.py`_ - demonstrates :class:`StreamServer`
- `wsgiserver.py`_ - demonstrates :class:`wsgi.WSGIServer <gevent.wsgi.WSGIServer>`
- `wsgiserver_ssl.py`_ - demonstrates :class:`pywsgi.WSGIServer <gevent.pywsgi.WSGIServer>`

.. _`code repository`: http://bitbucket.org/denis/gevent/src/tip/examples/#source-path
.. _`does not support streaming`: http://code.google.com/p/gevent/issues/detail?id=4
.. _`pipelining does not work`: http://code.google.com/p/gevent/issues/detail?id=32
.. _gunicorn: http://gunicorn.org
.. _`echoserver.py`: http://bitbucket.org/denis/gevent/src/tip/examples/echoserver.py#cl-9
.. _`wsgiserver.py`: http://bitbucket.org/denis/gevent/src/tip/examples/wsgiserver.py#cl-4
.. _`wsgiserver_ssl.py`: http://bitbucket.org/denis/gevent/src/tip/examples/wsgiserver_ssl.py#cl-4
.. _`httpserver.py`: http://bitbucket.org/denis/gevent/src/tip/examples/httpserver.py#cl-4

.. toctree::

   gevent.server
   gevent.pywsgi
   gevent.wsgi


