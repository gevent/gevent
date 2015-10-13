==============
 Introduction
==============

gevent is a coroutine-based Python networking library.

Features include:

* Fast event loop based on libev (epoll on Linux, kqueue on FreeBSD,
  select on Mac OS X).
* Lightweight execution units based on greenlet.
* API that re-uses concepts from the Python standard library (e.g. :class:`gevent.event.Event`, :class:`gevent.queue.Queue`).
* Cooperative :mod:`socket` and :mod:`ssl` modules.
* Ability to use standard library and 3rd party modules written for standard blocking sockets (:mod:`gevent.monkey`).
* DNS queries performed through threadpool (default) or through c-ares (enabled via GEVENT_RESOLVER=ares env var).
* TCP/UDP/HTTP servers
* Subprocess support (through :mod:`gevent.subprocess`)
* Thread pools

.. _installation:

Installation and Requirements
=============================

gevent runs on Python 2 and Python 3. Versions 2.6 and 2.7 of Python 2
are supported, and versions 3.3, 3.4, and 3.5 of Python 3 are
supported. gevent requires the greenlet__ library.

gevent also runs on PyPy 2.5.0 and above, although 2.6.1 or above is
strongly recommended. On PyPy, there are no external dependencies.

gevent and greenlet can both be installed with `pip`_, e.g., ``pip
install gevent``. On Windows, both gevent and greenlet are distributed
as binary `wheels`_, so no C compiler is required (so long as pip is
at least version 1.4). On Linux and Mac OS X, a C compiler (Xcode on
OS X) and the Python development package are required.

__ http://pypi.python.org/pypi/greenlet
.. _`pip`: https://pip.pypa.io/en/stable/installing/
.. _`wheels`: http://pythonwheels.com

Example
=======

The following example shows how to run tasks concurrently.

    >>> import gevent
    >>> from gevent import socket
    >>> urls = ['www.google.com', 'www.example.com', 'www.python.org']
    >>> jobs = [gevent.spawn(socket.gethostbyname, url) for url in urls]
    >>> gevent.joinall(jobs, timeout=2)
    >>> [job.value for job in jobs]
    ['74.125.79.106', '208.77.188.166', '82.94.164.162']

After the jobs have been spawned, :func:`gevent.joinall` waits for
them to complete, allowing up to 2 seconds. The results are
then collected by checking the :attr:`~gevent.Greenlet.value` property.
The :func:`gevent.socket.gethostbyname` function has the same
interface as the standard :func:`socket.gethostbyname` but it does not
block the whole interpreter and thus lets the other greenlets proceed
with their requests unhindered.

.. _monkey-patching:


Monkey patching
===============

The example above used :mod:`gevent.socket` for socket operations. If the standard :mod:`socket`
module was used the example would have taken 3 times longer to complete because the DNS requests would
be sequential (serialized). Using the standard socket module inside greenlets makes gevent rather
pointless, so what about existing modules and packages that are built
on top of :mod:`socket` (including the standard library modules like :mod:`urllib`)?

That's where monkey patching comes in. The functions in :mod:`gevent.monkey` carefully
replace functions and classes in the standard :mod:`socket` module with their cooperative
counterparts. That way even the modules that are unaware of gevent can benefit from running
in a multi-greenlet environment.

    >>> from gevent import monkey; monkey.patch_socket()
    >>> import urllib2 # it's usable from multiple greenlets now

See `examples/concurrent_download.py`__

Beyond sockets
--------------

Of course, there are several other parts of the standard library that can
block the whole interpreter and result in serialized behavior. gevent
provides cooperative versions of many of those as well. They can be
patched independently through individual functions, but most programs
using monkey patching will want to patch the entire recommended set of
modules using the :func:`gevent.monkey.patch_all` function::

    >>> from gevent import monkey; monkey.patch_all()
    >>> import subprocess # it's usable from multiple greenlets now


.. note:: When monkey patching, it is recommended to do so as early as
		  possible in the lifetime of the process. If possible,
		  monkey patching should be the first lines executed.

__ https://github.com/gevent/gevent/blob/master/examples/concurrent_download.py#L1

Event loop
==========

Instead of blocking and waiting for socket operations to complete (a
technique known as polling), gevent arranges for the operating system
to deliver an event letting it know when, for example, data has
arrived to be read from the socket. Having done that, gevent can move
on to running another greenlet, perhaps one that itself now has an
event ready for it. This repeated process of registering for events
and reacting to them as they arrive is the event loop.

Unlike other network libraries, though in a similar fashion as
eventlet, gevent starts the event loop implicitly in a dedicated
greenlet. There's no ``reactor`` that you must call a ``run()`` or
``dispatch()`` function on. When a function from gevent's API wants to
block, it obtains the :class:`gevent.hub.Hub` instance --- a special
greenlet that runs the event loop --- and switches to it (it is said
that the greenlet *yielded* control to the Hub). If there's no
:class:`~gevent.hub.Hub` instance yet, one is automatically created.

.. tip:: Each operating system thread has its own
         :class:`~gevent.hub.Hub`. This makes it possible to use the
         gevent blocking API from multiple threads (with care).

The event loop provided by libev uses the fastest polling mechanism
available on the system by default. Please read the `libev documentation`_ for more
information.

.. As of 1.1 or before, we set the EVFLAG_NOENV so this isn't possible any more.

   It is possible to command libev to
   use a particular polling mechanism by setting the ``LIBEV_FLAGS``
   environment variable. Possible values include ``LIBEV_FLAGS=1`` for
   the select backend, ``LIBEV_FLAGS=2`` for the poll backend,
   ``LIBEV_FLAGS=4`` for the epoll backend and ``LIBEV_FLAGS=8`` for the
   kqueue backend.

.. _`libev documentation`: http://pod.tst.eu/http://cvs.schmorp.de/libev/ev.pod#FUNCTIONS_CONTROLLING_EVENT_LOOPS

The Libev API is available under the :mod:`gevent.core` module. Note that
the callbacks supplied to the libev API are run in the :class:`gevent.hub.Hub`
greenlet and thus cannot use the synchronous gevent API. It is possible to
use the asynchronous API there, like :func:`gevent.spawn` and
:meth:`gevent.event.Event.set`.


Cooperative multitasking
========================

.. currentmodule:: gevent

The greenlets all run in the same OS thread and are scheduled
cooperatively. This means that until a particular greenlet gives up
control, (by calling a blocking function that will switch to the
:class:`~gevent.hub.Hub`), other greenlets won't get a chance to run. This is
typically not an issue for an I/O bound app, but one should be aware
of this when doing something CPU intensive, or when calling blocking
I/O functions that bypass the libev event loop.

.. tip:: Even some apparently cooperative functions, like
		 :func:`gevent.sleep`, can temporarily take priority over
		 waiting I/O operations in some circumstances.

Synchronizing access to objects shared across the greenlets is
unnecessary in most cases (because yielding control is usually
explict), thus traditional synchronization devices like the
:class:`~lock.BoundedSemaphore`, :class:`~lock.RLock` and
:class:`~lock.Semaphore` classes, although present, aren't used very
often. Other abstractions from threading and multiprocessing remain
useful in the cooperative world:

- :class:`~event.Event` allows one to wake up a number of greenlets that are calling :meth:`~event.Event.wait` method.
- :class:`~event.AsyncResult` is similar to :class:`~event.Event` but allows passing a value or an exception to the waiters.
- :class:`~queue.Queue` and :class:`~queue.JoinableQueue`.


Lightweight pseudothreads
=========================

.. currentmodule:: gevent.greenlet

New greenlets are spawned by creating a :class:`~gevent.Greenlet` instance and calling its :meth:`start <gevent.Greenlet.start>`
method. (The :func:`gevent.spawn` function is a shortcut that does exactly that). The :meth:`start <gevent.Greenlet.start>`
method schedules a switch to the greenlet that will happen as soon as the current greenlet gives up control.
If there is more than one active greenlet, they will be executed one
by one, in an undefined order as they each give up control to the :class:`~gevent.hub.Hub`.

If there is an error during execution it won't escape the greenlet's boundaries. An unhandled error results
in a stacktrace being printed, annotated by the failed function's signature and arguments:

    >>> gevent.spawn(lambda : 1/0)
    >>> gevent.sleep(1)
    Traceback (most recent call last):
     ...
    ZeroDivisionError: integer division or modulo by zero
    <Greenlet at 0x7f2ec3a4e490: <function <lambda...>> failed with ZeroDivisionError

The traceback is asynchronously printed to ``sys.stderr`` when the greenlet dies.

:class:`Greenlet` instances have a number of useful methods:

- :meth:`join <gevent.Greenlet.join>` -- waits until the greenlet exits;
- :meth:`kill <gevent.Greenlet.kill>` -- interrupts greenlet's execution;
- :meth:`get <gevent.Greenlet.get>`  -- returns the value returned by greenlet or re-raises the exception that killed it.

It is possible to customize the string printed after the traceback by subclassing the :class:`~gevent.Greenlet` class
and redefining its ``__str__`` method.

To subclass a :class:`gevent.Greenlet`, override its
:meth:`gevent.Greenlet._run` method and call
``Greenlet.__init__(self)`` in ``__init__``::

    class MyNoopGreenlet(Greenlet):

        def __init__(self, seconds):
            Greenlet.__init__(self)
            self.seconds = seconds

        def _run(self):
            gevent.sleep(self.seconds)

        def __str__(self):
            return 'MyNoopGreenlet(%s)' % self.seconds

Greenlets can be killed synchronously from another greenlet. Killing will resume the sleeping greenlet, but instead
of continuing execution, a :exc:`~gevent.greenlet.GreenletExit` will be raised.

    >>> g = MyNoopGreenlet(4)
    >>> g.start()
    >>> g.kill()
    >>> g.dead
    True

The :exc:`gevent.greenlet.GreenletExit` exception and its subclasses are handled differently than other exceptions.
Raising :exc:`~gevent.greenlet.GreenletExit` is not considered an exceptional situation, so the traceback is not printed.
The :exc:`~gevent.greenlet.GreenletExit` is returned by :meth:`get <gevent.Greenlet.get>` as if it were returned by the greenlet, not raised.

The :meth:`kill <gevent.Greenlet.kill>` method can accept a custom exception to be raised:

    >>> g = MyNoopGreenlet.spawn(5) # spawn() creates a Greenlet and starts it
    >>> g.kill(Exception("A time to kill"))
    Traceback (most recent call last):
     ...
    Exception: A time to kill
    MyNoopGreenlet(5) failed with Exception

The :meth:`kill <gevent.Greenlet.kill>` can also accept a *timeout*
argument specifying the number of seconds to wait for the greenlet to
exit. Note that :meth:`kill <gevent.Greenlet.kill>` cannot guarantee
that the target greenlet will not ignore the exception (i.e., it might
catch it), thus it's a good idea always to pass a timeout to
:meth:`kill <gevent.Greenlet.kill>` (otherwise, the greenlet doing the
killing will remain blocked forever).

.. tip:: The exact timing at which an exception is raised within a
		  target greenlet as the result of :meth:`kill
		  <gevent.Greenlet.kill>` is not defined. See that function's
		  documentation for more details.

Timeouts
========

Many functions in the gevent API are synchronous, blocking the current
greenlet until the operation is done. For example, :meth:`kill
<gevent.Greenlet.kill>` waits until the target greenlet is
:attr:`~gevent.greenlet.Greenlet.dead` before returning [#f1]_. Many of
those functions can be made asynchronous by passing the keyword argument
``block=False``.

Furthermore, many of the synchronous functions accept a *timeout*
argument, which specifies a limit on how long the function can block
(examples include :meth:`gevent.event.Event.wait`,
:meth:`gevent.Greenlet.join`, :meth:`gevent.Greenlet.kill`,
:meth:`gevent.event.AsyncResult.get`, and many more).

The :class:`socket <gevent.socket.socket>` and :class:`SSLObject
<gevent.ssl.SSLObject>` instances can also have a timeout, set by the
:meth:`settimeout <gevent.socket.socket.settimeout>` method.

When these are not enough, the :class:`~gevent.timeout.Timeout` class can be used to
add timeouts to arbitrary sections of (cooperative, yielding) code.


Futher reading
==============

To limit concurrency, use the :class:`gevent.pool.Pool` class (see `example: dns_mass_resolve.py`_).

Gevent comes with TCP/SSL/HTTP/WSGI servers. See :doc:`servers`.

.. _`example: dns_mass_resolve.py`: https://github.com/gevent/gevent/blob/master/examples/dns_mass_resolve.py#L17


External resources
==================

`Gevent for working Python developer`__ is a comprehensive tutorial.

__ http://sdiehl.github.io/gevent-tutorial/

.. rubric:: Footnotes

.. [#f1] This was not the case before 0.13.0, :meth:`kill <Greenlet>` method in 0.12.2 and older was asynchronous by default.
