==================================
 :mod:`gevent` -- basic utilities
==================================

.. module:: gevent

The most common functions and classes are available in the :mod:`gevent` top level package.

.. autodata:: __version__

.. autodata:: version_info

Greenlet objects
================

:class:`Greenlet` is a light-weight cooperatively-scheduled execution unit.

To start a new greenlet, pass the target function and its arguments to :class:`Greenlet` constructor and call :meth:`start`:

>>> g = Greenlet(myfunction, 'arg1', 'arg2', kwarg1=1)
>>> g.start()

or use classmethod :meth:`spawn` which is a shortcut that does the same:

>>> g = Greenlet.spawn(myfunction, 'arg1', 'arg2', kwarg1=1)

To subclass a :class:`Greenlet`, override its ``_run()`` method and
call ``Greenlet.__init__(self)`` in :meth:`__init__`: It also a good
idea to override :meth:`__str__`: if :meth:`_run` raises an exception,
its string representation will be printed after the traceback it
generated.

    .. important:: You *SHOULD NOT* attempt to override the ``run()`` method.

.. class:: Greenlet

.. automethod:: Greenlet.__init__

.. attribute:: Greenlet.value

    Holds the value returned by the function if the greenlet has
    finished successfully. Until then, or if it finished in error, ``None``.

    .. tip:: Recall that a greenlet killed with the default
             :class:`GreenletExit` is considered to have finished
             successfully, and the ``GreenletExit`` exception will be
             its value.

.. autoattribute:: Greenlet.exception

.. automethod:: Greenlet.ready
.. automethod:: Greenlet.successful
.. automethod:: Greenlet.start
.. automethod:: Greenlet.start_later
.. automethod:: Greenlet.join
.. automethod:: Greenlet.get
.. automethod:: Greenlet.kill(exception=GreenletExit, block=True, timeout=None)
.. automethod:: Greenlet.link(callback)
.. automethod:: Greenlet.link_value(callback)
.. automethod:: Greenlet.link_exception(callback)
.. automethod:: Greenlet.rawlink
.. automethod:: Greenlet.unlink

Boolean Contexts
----------------

Greenlet objects have a boolean value (``__nonzero__`` or
``__bool__``) which is true if it's active: started but not dead yet.

It's possible to use it like this::

    >>> g = gevent.spawn(...)
    >>> while g:
           # do something while g is alive

The Greenlet's ``__nonzero__`` is an improvement on greenlet's
``__nonzero__``. The greenlet's :meth:`__nonzero__
<greenlet.greenlet.__nonzero__>` returns False if greenlet has not
been switched to yet or is already dead. While the latter is OK, the
former is not good, because a just spawned Greenlet has not been
switched to yet and thus would evaluate to False.

Raw greenlet Methods
--------------------

Being a greenlet__ subclass, :class:`Greenlet` also has `switch()
<switching>`_ and `throw() <throw>`_ methods. However, these should
not be used at the application level as they can very easily lead to
greenlets that are forever unscheduled. Prefer higher-level safe
classes, like :class:`Event <gevent.event.Event>` and :class:`Queue
<gevent.queue.Queue>`, instead.

__ http://greenlet.readthedocs.org/en/latest/#instantiation
.. _switching: https://greenlet.readthedocs.org/en/latest/#switching
.. _throw: https://greenlet.readthedocs.org/en/latest/#methods-and-attributes-of-greenlets

.. exception:: GreenletExit

    A special exception that kills the greenlet silently.

    When a greenlet raises :exc:`GreenletExit` or a subclass, the traceback is not
    printed and the greenlet is considered :meth:`successful <Greenlet.successful>`.
    The exception instance is available under :attr:`value <Greenlet.value>`
    property as if it was returned by the greenlet, not raised.

Spawn helpers
=============

.. autofunction:: spawn(function, *args, **kwargs)
.. autofunction:: spawn_later(seconds, function, *args, **kwargs)
.. autofunction:: spawn_raw


Useful general functions
========================

.. function:: getcurrent()

   Return the currently executing greenlet (the one that called this
   function). Note that this may be an instance of :class:`Greenlet`
   or :class:`greenlet.greenlet`.

Sleeping
--------

.. autofunction:: sleep

.. autofunction:: idle

Stopping Greenlets
------------------

.. autofunction:: kill(greenlet, exception=GreenletExit)

.. autofunction:: killall(greenlets, exception=GreenletExit, block=True, timeout=None)

Waiting
-------

.. autofunction:: wait

.. autofunction:: iwait

.. autofunction:: joinall

Working with muliple processes
------------------------------

.. autofunction:: fork

.. autofunction:: reinit

Signals
-------

.. function:: signal(signalnum, handler, *args, **kwargs)

    Call the *handler* with the *args* and *kwargs* when the process
    receives the signal *signalnum*.

    The *handler* will be run in a new greenlet when the signal is delivered.

    This returns an object with the useful method ``cancel``, which, when called,
    will prevent future deliveries of *signalnum* from calling *handler*.

    .. note::

        This may not operate correctly with SIGCHLD if libev child watchers
        are used (as they are by default with :func:`gevent.os.fork`).

    .. versionchanged:: 1.1b4

         This is an alias for ``gevent.hub.signal``, included for
         backwards compatibility; the new module :doc:`gevent.signal <gevent.signal>`
         is replacing this name. This alias will be removed in a
         future release.

.. This is also in the docstring of gevent.hub.signal, which is the
   actual callable invoked

Timeouts
========

.. autoclass:: Timeout
    :members:
    :undoc-members:

.. autofunction:: with_timeout
