==============
 Introduction
==============

.. include:: _about.rst

.. _installation:

Installation and Requirements
=============================

`gevent 1.3`_ runs on Python 2.7 and Python 3. Releases 3.4, 3.5 and
3.6 of Python 3 are supported. (Users of older versions of Python 2
need to install gevent 1.0.x (2.5), 1.1.x (2.6) or 1.2.x (<=2.7.8);
gevent 1.2 can be installed on Python 3.3.) gevent requires the
greenlet__ library and will install the `cffi`_ library by default on
Windows.

gevent 1.3 also runs on PyPy 5.5 and above, although 5.9 or above is
strongly recommended. On PyPy, there are no external dependencies.

gevent is tested on Windows, OS X, and Linux, and should run on most
other Unix-like operating systems (e.g., FreeBSD, Solaris, etc.)

.. note:: On Windows using the libev backend, gevent is
          limited to a maximum of 1024 open sockets due to
          `limitations in libev`_. This limitation should not exist
          with the default libuv backend.

gevent and greenlet can both be installed with `pip`_, e.g., ``pip
install gevent``. On Windows, OS X, and Linux, both gevent and greenlet are
distributed as binary `wheels`_, so no C compiler is required (so long
as pip is at least version 8.0). For other platforms
without pre-built wheels or if wheel installation is disabled, a C compiler
(Xcode on OS X) and the Python development package are required.
`cffi`_ can optionally be installed to build the CFFI backend in
addition to the Cython backend on CPython; it is necessary to use the
libuv backend.

.. note::

   On Linux, you'll need to install gevent from source if you wish to
   use the libuv loop implementation. This is because the `manylinux1
   <https://www.python.org/dev/peps/pep-0513/>`_ specification for the
   distributed wheels does not support libuv. The `cffi`_ library
   *must* be installed at build time.

The `psutil <https://pypi.org/project/psutil>`_ library is needed to
monitor memory usage.

`zope.event <https://pypi.org/project/zope.event>`_ is highly
recommended for configurable event support; it can be installed with
the ``events`` extra, e.g., ``pip install gevent[events]``.

`dnspython <https://pypi.org/project/dnspython>`_ is required for the
new pure-Python resolver, and on Python 2, so is `idna
<https://pypi.org/project/idna>`_. They can be installed with the
``dnspython`` extra.

Development instructions (including building from a source checkout)
can be found `on PyPI <https://pypi.python.org/pypi/gevent#development>`_.

__ http://pypi.python.org/pypi/greenlet
.. _`pip`: https://pip.pypa.io/en/stable/installing/
.. _`wheels`: http://pythonwheels.com
.. _`gevent 1.3`: whatsnew_1_3.html
.. _`cffi`: https://cffi.readthedocs.io
.. _`limitations in libev`: http://pod.tst.eu/http://cvs.schmorp.de/libev/ev.pod#WIN32_PLATFORM_LIMITATIONS_AND_WORKA

Common Installation Issues
--------------------------

The following are some common installation problems and solutions for
those compiling gevent from source.

- Some Linux distributions are now mounting their temporary
  directories with the ``noexec`` option. This can cause a
  standard ``pip install gevent`` to fail with an error like
  ``cannot run C compiled programs``. One fix is to mount the
  temporary directory without that option. Another may be to
  use the ``--build`` option to ``pip install`` to specify
  another directory. See :issue:`570` and :issue:`612` for
  examples.

- Also check for conflicts with environment variables like ``CFLAGS``. For
  example, see :ref:`library_updates_label`.

- Users of a recent SmartOS release may need to customize
  the ``CPPFLAGS`` (the environment variable containing the
  default options for the C preprocessor) if they are using the
  libev shipped with gevent. See :ref:`operating_systems_label` for
  more information.

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

See :doc:`examples/concurrent_download`.

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


.. tip::

   When monkey patching, it is recommended to do so as early as
   possible in the lifetime of the process. If possible,
   monkey patching should be the first lines executed. Monkey
   patching later, especially if native threads have been
   created, :mod:`atexit` or signal handlers have been installed,
   or sockets have been created, may lead to unpredictable
   results including unexpected :exc:`~gevent.hub.LoopExit` errors.


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

The event loop uses the best polling mechanism available on the system
by default.

.. note::

   A low-level event loop API is available under the
   :mod:`gevent.core` module. This module is not documented, not meant
   for general purpose usage, and it's exact contents and semantics
   change slightly depending on whether the libev or libuv event loop
   is being used. The callbacks supplied to the event loop API are run
   in the :class:`~gevent.hub.Hub` greenlet and thus cannot use the
   synchronous gevent API. It is possible to use the asynchronous API
   there, like :func:`gevent.spawn` and
   :meth:`gevent.event.Event.set`.


Cooperative multitasking
========================

.. currentmodule:: gevent

The greenlets all run in the same OS thread and are scheduled
cooperatively. This means that until a particular greenlet gives up
control, (by calling a blocking function that will switch to the
:class:`~gevent.hub.Hub`), other greenlets won't get a chance to run.
This is typically not an issue for an I/O bound app, but one should be
aware of this when doing something CPU intensive, or when calling
blocking I/O functions that bypass the event loop.

.. tip:: Even some apparently cooperative functions, like
		 :func:`gevent.sleep`, can temporarily take priority over
		 waiting I/O operations in some circumstances.

Synchronizing access to objects shared across the greenlets is
unnecessary in most cases (because yielding control is usually
explict), thus traditional synchronization devices like the
:class:`gevent.lock.BoundedSemaphore`, :class:`gevent.lock.RLock` and
:class:`gevent.lock.Semaphore` classes, although present, aren't used very
often. Other abstractions from threading and multiprocessing remain
useful in the cooperative world:

- :class:`~event.Event` allows one to wake up a number of greenlets
  that are calling :meth:`~event.Event.wait` method.
- :class:`~event.AsyncResult` is similar to :class:`~event.Event` but
  allows passing a value or an exception to the waiters.
- :class:`~queue.Queue` and :class:`~queue.JoinableQueue`.

.. _greenlet-basics:

Lightweight pseudothreads
=========================

.. currentmodule:: gevent

New greenlets are spawned by creating a :class:`~Greenlet` instance
and calling its :meth:`start <gevent.Greenlet.start>` method. (The
:func:`gevent.spawn` function is a shortcut that does exactly that).
The :meth:`start <gevent.Greenlet.start>` method schedules a switch to
the greenlet that will happen as soon as the current greenlet gives up
control. If there is more than one active greenlet, they will be
executed one by one, in an undefined order as they each give up
control to the :class:`~gevent.hub.Hub`.

If there is an error during execution it won't escape the greenlet's
boundaries. An unhandled error results in a stacktrace being printed,
annotated by the failed function's signature and arguments:

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

Greenlets can be subclassed with care. One use for this is to
customize the string printed after the traceback by subclassing the
:class:`~gevent.Greenlet` class and redefining its ``__str__`` method.
For more information, see :ref:`subclassing-greenlet`.


Greenlets can be killed synchronously from another greenlet. Killing
will resume the sleeping greenlet, but instead of continuing
execution, a :exc:`GreenletExit` will be raised.

    >>> g = Greenlet(gevent.sleep, 4)
    >>> g.start()
    >>> g.kill()
    >>> g.dead
    True

The :exc:`GreenletExit` exception and its subclasses are handled
differently than other exceptions. Raising :exc:`~GreenletExit` is not
considered an exceptional situation, so the traceback is not printed.
The :exc:`~GreenletExit` is returned by :meth:`get
<gevent.Greenlet.get>` as if it were returned by the greenlet, not
raised.

The :meth:`kill <gevent.Greenlet.kill>` method can accept a custom exception to be raised:

    >>> g = Greenlet.spawn(gevent.sleep, 5) # spawn() creates a Greenlet and starts it
    >>> g.kill(Exception("A time to kill"))
    Traceback (most recent call last):
     ...
    Exception: A time to kill
    Greenlet(5) failed with Exception

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

.. caution::
   Use care when killing greenlets, especially arbitrary
   greenlets spawned by a library or otherwise executing code you are
   not familiar with. If the code being executed is not prepared to
   deal with exceptions, object state may be corrupted. For example,
   if it has acquired a ``Lock`` but *does not* use a ``finally``
   block to release it, killing the greenlet at the wrong time could
   result in the lock being permanently locked::

     def func():
         # DON'T DO THIS
         lock.acquire()
         socket.sendall(data) # This could raise many exceptions, including GreenletExit
         lock.release()

   `This document
   <http://docs.oracle.com/javase/8/docs/technotes/guides/concurrency/threadPrimitiveDeprecation.html>`_
   describes a similar situation for threads.

Timeouts
========

Many functions in the gevent API are synchronous, blocking the current
greenlet until the operation is done. For example, :meth:`kill
<gevent.Greenlet.kill>` waits until the target greenlet is
:attr:`~gevent.Greenlet.dead` before returning [#f1]_. Many of
those functions can be made asynchronous by passing the keyword argument
``block=False``.

Furthermore, many of the synchronous functions accept a *timeout*
argument, which specifies a limit on how long the function can block
(examples include :meth:`gevent.event.Event.wait`,
:meth:`gevent.Greenlet.join`, :meth:`gevent.Greenlet.kill`,
:meth:`gevent.event.AsyncResult.get`, and many more).

The :class:`socket <gevent.socket.socket>` and :class:`SSLObject
<gevent.ssl.SSLObject>` instances can also have a timeout, set by the
:meth:`settimeout <socket.socket.settimeout>` method.

When these are not enough, the :class:`gevent.Timeout` class and
:func:`gevent.with_timeout` can be used to add timeouts to arbitrary
sections of (cooperative, yielding) code.


Further Reading
===============

To limit concurrency, use the :class:`gevent.pool.Pool` class (see
:doc:`examples/dns_mass_resolve`).

Gevent comes with TCP/SSL/HTTP/WSGI servers. See :doc:`servers`.

There are a number of configuration options for gevent. See
:ref:`gevent-configuration` for details. This document also explains how
to enable gevent's builtin monitoring and debugging features.

The objects in :mod:`gevent.util` may be helpful for monitoring and
debugging purposes.

See :doc:`api/index` for a complete API reference.


External resources
==================

`Gevent for working Python developer`__ is a comprehensive tutorial.

__ http://sdiehl.github.io/gevent-tutorial/

.. rubric:: Footnotes

.. [#f1] This was not the case before 0.13.0, :meth:`kill <gevent.Greenlet.kill>` method in 0.12.2 and older was asynchronous by default.

..  LocalWords:  Greenlets
