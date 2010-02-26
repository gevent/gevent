Introduction
============

The following example shows how to run tasks concurrently.

    >>> import gevent
    >>> from gevent import socket
    >>> urls = ['www.google.com', 'www.example.com', 'www.python.org']
    >>> jobs = [gevent.spawn(socket.gethostbyname, url) for url in urls]
    >>> gevent.joinall(jobs, timeout=2)
    >>> [job.value for job in jobs]
    ['74.125.79.106', '208.77.188.166', '82.94.164.162']

After the jobs have been spawned, :func:`gevent.joinall` waits for them to complete,
no longer than 2 seconds though. The results are then collected by checking
:attr:`gevent.Greenlet.value` property. The :func:`gevent.socket.gethostbyname` function
has the same interface as the standard :func:`socket.gethostbyname` but it does not block
the whole interpreter and thus lets the other greenlets to proceed with their requests as well.

If there was an error during execution it won't escape greenlet's boundaries.
An unhandled error results in a stacktrace being printed complemented by
failed function signature and arguments:

    >>> gevent.spawn(lambda : 1/0).join() # join() waits for the greenlet to complete
    Traceback (most recent call last):
     ...
    ZeroDivisionError: integer division or modulo by zero
    <Greenlet at 0x7f2ec3a4e490: <function <lambda> at 0x7f2ec3aa8398>> failed with ZeroDivisionError


.. _monkey-patching:

Monkey patching
---------------

The example above used :mod:`gevent.socket` for socket operations. If the standard :mod:`socket`
module was used it would took it 3 times longer to complete because the DNS requests would
be sequential. Using the standard socket module inside greenlets makes gevent rather
pointless, so what about module and packages that are built on top of :mod:`socket`?

That's what monkey patching for. The functions in :mod:`gevent.monkey` carefully
replace functions and classes in the standard :mod:`socket` module with their cooperative
counterparts. That way even the modules that are unaware of gevent can benefit from running
in multi-greenlet environment.

    >>> from gevent import monkey; monkey.patch_socket()
    >>> import urllib2 # it's usable from multiple greenlets now

See `examples/concurrent_download.py`__

__ http://bitbucket.org/denis/gevent/src/tip/examples/concurrent_download.py


Usage notes
-----------

Note, that greenlets are cooperatively scheduled. This means that until a
particular greenlet gives up control, other greenlets won't get a chance to run.
It is typically not an issue for an I/O bound app, but one should be aware
of this when doing something CPU intensive or calling blocking I/O functions
that bypass libevent event loop.

.. currentmodule:: gevent.hub

Unlike other network libraries and similar to eventlet, gevent starts
the event loop implicitly in a dedicated greenlet. There's no ``reactor`` that
you must ``run()`` or ``dispatch()`` function to call. When a function from
gevent API wants to block, it obtains the :class:`Hub` - a greenlet
that runs the event loop - and switches to it. If there's no :class:`Hub`
instance yet, one is created on the fly.

.. currentmodule:: gevent

The blocking gevent API does not work in the :class:`Hub <hub.Hub>` greenlet. Typically
it's not a problem as most of the library takes care not to run user-supplied
callbacks in the :class:`Hub <hub.Hub>`. The exception is :meth:`Greenlet.rawlink`
and :meth:`Event.rawlink <event.Event.rawlink>` methods as well as everything
in the :mod:`gevent.core` module.
