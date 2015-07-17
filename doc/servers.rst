.. implementing-servers:

======================
 Implementing servers
======================

.. currentmodule:: gevent.baseserver

There are a few classes to simplify server implementation with gevent.
They all share a similar interface, inherited from :class:`BaseServer`::

  def handle(socket, address):
       print('new connection!')

  server = StreamServer(('127.0.0.1', 1234), handle) # creates a new server
  server.start() # start accepting new connections

At this point, any new connection accepted on ``127.0.0.1:1234`` will result in a new
:class:`gevent.Greenlet` spawned running the *handle* function. To stop a server use :meth:`BaseServer.stop` method.

In case of a :class:`gevent.pywsgi.WSGIServer`, *handle* must be a WSGI application callable.

It is possible to limit the maximum number of concurrent connections,
by passing a :class:`gevent.pool.Pool` instance. In addition, passing
a pool allows the :meth:`BaseServer.stop` method to kill requests that
are in progress::

  pool = Pool(10000) # do not accept more than 10000 connections
  server = StreamServer(('127.0.0.1', 1234), handle, spawn=pool)
  server.serve_forever()


.. tip:: If you don't want to limit concurrency, but you *do* want to
         be able to kill outstanding requests, use a pool created with
         a size of ``None``.


The :meth:`BaseServer.serve_forever` method calls
:meth:`BaseServer.start` and then waits until interrupted or until the
server is stopped.

The :mod:`gevent.pywsgi` module contains an implementation of a :pep:`3333`
:class:`WSGI server <gevent.pywsgi.WSGIServer>`. In addition,
gunicorn_ is a stand-alone server that supports gevent. Gunicorn has
its own HTTP parser but can also use :mod:`gevent.wsgi` module.

More examples are available in the `code repository`_:

- `echoserver.py`_ - demonstrates :class:`StreamServer`
- `wsgiserver.py`_ - demonstrates :class:`wsgi.WSGIServer <gevent.wsgi.WSGIServer>`
- `wsgiserver_ssl.py`_ - demonstrates :class:`pywsgi.WSGIServer <gevent.pywsgi.WSGIServer>`

.. _`code repository`: https://github.com/gevent/gevent/tree/master/examples
.. _gunicorn: http://gunicorn.org
.. _`echoserver.py`: https://github.com/gevent/gevent/blob/master/examples/echoserver.py#L34
.. _`wsgiserver.py`: https://github.com/gevent/gevent/blob/master/examples/wsgiserver.py#L18
.. _`wsgiserver_ssl.py`: https://github.com/gevent/gevent/blob/master/examples/wsgiserver_ssl.py#L17

.. toctree::

   gevent.baseserver
   gevent.server
   gevent.pywsgi
   gevent.wsgi
