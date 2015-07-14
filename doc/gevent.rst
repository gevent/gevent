:mod:`gevent` -- basic utilities
================================

.. module:: gevent

The most common functions and classes are available in the :mod:`gevent` top level package.

.. autodata:: __version__


Greenlet objects
----------------

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

    .. note:: You SHOULD NOT attempt to override the ``run()`` method.

.. class:: Greenlet

.. automethod:: Greenlet.__init__

.. attribute:: Greenlet.value

    Holds the value returned by the function if the greenlet has finished successfully. Otherwise ``None``.

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
.. automethod:: Greenlet.unlink


Greenlet objects have a boolean value (``__nonzero__`` or ``__bool__``) which is true if it's active: started but not dead yet.

It's possible to use it like this::

  g = gevent.spawn(...)
  while g:
      # do something while g is alive

The Greenlet's ``__nonzero__`` is an improvement on greenlet's
``__nonzero__``. The greenlet's `__nonzero__` returns False if greenlet has
not been switched to yet or already dead. While the latter is OK, the
former is not good, because a just spawned Greenlet has not been
switched to yet and thus would evaluate to False.

Being a greenlet__ subclass, :class:`Greenlet` also has ``switch()`` and ``throw()`` methods.
However, these should not be used at the application level. Prefer higher-level safe
classes, like :class:`Event <gevent.event.Event>` and :class:`Queue <gevent.queue.Queue>`, instead.

__ http://greenlet.readthedocs.org/en/latest/#instantiation

.. exception:: GreenletExit

    A special exception that kills the greenlet silently.

    When a greenlet raises :exc:`GreenletExit` or a subclass, the traceback is not
    printed and the greenlet is considered :meth:`successful <Greenlet.successful>`.
    The exception instance is available under :attr:`value <Greenlet.value>`
    property as if it was returned by the greenlet, not raised.

Spawn helpers
-------------

.. autofunction:: spawn(function, *args, **kwargs)
.. autofunction:: spawn_later(seconds, function, *args, **kwargs)
.. autofunction:: spawn_raw




Useful general functions
------------------------

.. function:: getcurrent()

   Return the currently executing greenlet (the one that called this
   function). Note that this may be an instance of :class:`Greenlet`
   or :class:`greenlet.greenlet`.

.. autofunction:: sleep

.. autofunction:: kill(greenlet, exception=GreenletExit)

.. autofunction:: killall(greenlets, exception=GreenletExit, block=True, timeout=None)

.. autofunction:: joinall

.. autofunction:: signal

.. autofunction:: fork

.. autofunction:: reinit


Timeouts
--------

.. autoclass:: Timeout
    :members:
    :undoc-members:

.. autofunction:: with_timeout


Waiting
-------

.. autofunction:: wait

.. autofunction:: iwait
