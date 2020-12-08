===================================
 :mod:`gevent` -- common functions
===================================

.. module:: gevent

The most common functions and classes are available in the
:mod:`gevent` top level package.

Please read :doc:`/intro` for an introduction to the concepts
discussed here.

.. seealso:: :mod:`gevent.util`

.. seealso:: :doc:`/configuration`

             For configuring gevent using the environment or the
             ``gevent.config`` object.


.. autodata:: __version__


Working With Greenlets
======================

See :class:`gevent.Greenlet` for more information about greenlet
objects.

Creating Greenlets
------------------

.. autofunction:: spawn
.. autofunction:: spawn_later
.. autofunction:: spawn_raw


Getting Greenlets
-----------------

.. function:: getcurrent()

   Return the currently executing greenlet (the one that called this
   function). Note that this may be an instance of :class:`Greenlet`
   or :class:`greenlet.greenlet`.

Stopping Greenlets
------------------

.. autofunction:: kill(greenlet, exception=GreenletExit)

.. autofunction:: killall(greenlets, exception=GreenletExit, block=True, timeout=None)

Sleeping
========

.. autofunction:: sleep

.. autofunction:: idle

Switching
=========

.. function:: getswitchinterval() -> current switch interval


   See :func:`setswitchinterval`

   .. versionadded:: 1.3


.. function:: setswitchinterval(seconds)

   Set the approximate maximum amount of time that callback functions
   will be allowed to run before the event loop is cycled to
   poll for events. This prevents code that does things like the
   following from monopolizing the loop::

       while True: # Burning CPU!
           gevent.sleep(0) # But yield to other greenlets

   Prior to this, this code could prevent the event loop from running.

   On Python 3, this uses the native :func:`sys.setswitchinterval`
   and :func:`sys.getswitchinterval`.

   .. versionadded:: 1.3

Waiting
=======

.. autofunction:: wait

.. autofunction:: iwait

.. autofunction:: joinall

Working with multiple processes
===============================

.. note::
   These functions will only be available if :func:`os.fork` is
   available. In general, prefer to use :func:`gevent.os.fork` instead
   of manually calling these functions.

.. autofunction:: fork

.. autofunction:: reinit

Signals
=======

.. autofunction:: signal_handler

Timeouts
========

See class :class:`gevent.Timeout` for information about Timeout objects.

.. autofunction:: with_timeout

..  LocalWords:  Greenlet GreenletExit Greenlet's greenlet's
..  LocalWords:  automethod
