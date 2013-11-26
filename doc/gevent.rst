:mod:`gevent` -- basic utilities
================================

.. module:: gevent

The most common functions and classes are available in the :mod:`gevent` top level package.


Greenlet objects
----------------

:class:`Greenlet` is a light-weight cooperatively-scheduled execution unit.

To start a new greenlet, pass the target function and its arguments to :class:`Greenlet` constructor and call :meth:`start`:

>>> g = Greenlet(myfunction, 'arg1', 'arg2', kwarg1=1)
>>> g.start()

or use classmethod :meth:`spawn` which is a shortcut that does the same:

>>> g = Greenlet.spawn(myfunction, 'arg1', 'arg2', kwarg1=1)

To subclass a :class:`Greenlet`, override its _run() method and call ``Greenlet.__init__(self)`` in :meth:`__init__`:
It also a good idea to override :meth:`__str__`: if :meth:`_run` raises an exception, its string representation will be printed after the traceback it generated.

.. class:: Greenlet

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


Being a greenlet__ subclass, :class:`Greenlet` also has ``switch()`` and ``throw()`` methods.
However, these should not be used at the application level. Prefer higher-level safe
classes, like :class:`Event <gevent.event.Event>` and :class:`Queue <gevent.queue.Queue>`, instead.

__ http://codespeak.net/py/0.9.2/greenlet.html

.. exception:: GreenletExit

    A special exception that kills the greenlet silently.

    When a greenlet raises :exc:`GreenletExit` or a subclass, the traceback is not
    printed and the greenlet is considered :meth:`successful <Greenlet.successful>`.
    The exception instance is available under :attr:`value <Greenlet.value>`
    property as if it was returned by the greenlet, not raised.

Spawn helpers
-------------

.. function:: spawn(function, *args, **kwargs)

    Create a new :class:`Greenlet` object and schedule it to run ``function(*args, **kwargs)``.
    This is an alias for :meth:`Greenlet.spawn`.

.. function:: spawn_later(seconds, function, *args, **kwargs)

    Create a new :class:`Greenlet` object and schedule it to run ``function(*args, **kwargs)``
    in the future loop iteration *seconds* later.
    This is an alias for :meth:`Greenlet.spawn_later`.

.. function:: spawn_raw(function, *args, **kwargs)

    Create a new :class:`greenlet` object and schedule it to run ``function(*args, **kwargs)``.
    As this returns a raw greenlet, it does not have all the useful methods that
    :class:`gevent.Greenlet` has and should only be used as an optimization.


Useful general functions
------------------------

.. autofunction:: getcurrent

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
