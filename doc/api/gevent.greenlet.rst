==================
 Greenlet Objects
==================

.. currentmodule:: gevent

:class:`gevent.Greenlet` is a light-weight cooperatively-scheduled
execution unit. It is a more powerful version of
:class:`greenlet.greenlet`. For general information, see :ref:`greenlet-basics`.

You can retrieve the current greenlet at any time using
:func:`gevent.getcurrent`.

Starting Greenlets
==================

To start a new greenlet, pass the target function and its arguments to
:class:`Greenlet` constructor and call :meth:`Greenlet.start`:

>>> g = Greenlet(myfunction, 'arg1', 'arg2', kwarg1=1)
>>> g.start()

or use classmethod :meth:`Greenlet.spawn` which is a shortcut that
does the same:

>>> g = Greenlet.spawn(myfunction, 'arg1', 'arg2', kwarg1=1)

There are also various spawn helpers in :mod:`gevent`, including:

- :func:`gevent.spawn`
- :func:`gevent.spawn_later`
- :func:`gevent.spawn_raw`

Stopping Greenlets
==================

You can forcibly stop a :class:`Greenlet` using its :meth:`Greenlet.kill`
method. There are also helper functions that can be useful in limited
circumstances (if you might have a :class:`raw greenlet <greenlet.greenlet>`):

- :func:`gevent.kill`
- :func:`gevent.killall`

.. _subclassing-greenlet:

Subclassing Greenlet
====================

To subclass a :class:`Greenlet`, override its ``_run()`` method and
call ``Greenlet.__init__(self)`` in the subclass ``__init__``. This
can be done to override :meth:`Greenlet.__str__`: if ``_run`` raises
an exception, its string representation will be printed after the
traceback it generated.

::

    class MyNoopGreenlet(Greenlet):

        def __init__(self, seconds):
            Greenlet.__init__(self)
            self.seconds = seconds

        def _run(self):
            gevent.sleep(self.seconds)

        def __str__(self):
            return 'MyNoopGreenlet(%s)' % self.seconds


.. important:: You *SHOULD NOT* attempt to override the ``run()`` method.


Boolean Contexts
================

Greenlet objects have a boolean value (``__nonzero__`` or
``__bool__``) which is true if it's active: started but not dead yet.

It's possible to use it like this::

    >>> g = gevent.spawn(...)
    >>> while g:
           # do something while g is alive

The Greenlet's boolean value is an improvement on the raw
:class:`greenlet's <greenlet.greenlet>` boolean value. The raw
greenlet's boolean value returns False if the greenlet has not been
switched to yet or is already dead. While the latter is OK, the former
is not good, because a just spawned Greenlet has not been switched to
yet and thus would evaluate to False.

.. exception:: GreenletExit

    A special exception that kills the greenlet silently.

    When a greenlet raises :exc:`GreenletExit` or a subclass, the traceback is not
    printed and the greenlet is considered :meth:`successful <Greenlet.successful>`.
    The exception instance is available under :attr:`value <Greenlet.value>`
    property as if it was returned by the greenlet, not raised.


.. class:: Greenlet

.. automethod:: Greenlet.__init__

.. rubric:: Attributes

.. autoattribute:: Greenlet.exception
.. autoattribute:: Greenlet.minimal_ident
.. autoattribute:: Greenlet.name
.. autoattribute:: Greenlet.dead

.. attribute:: Greenlet.value

   Holds the value returned by the function if the greenlet has
   finished successfully. Until then, or if it finished in error, `None`.

   .. tip::

      Recall that a greenlet killed with the default
      :class:`GreenletExit` is considered to have finished
      successfully, and the `GreenletExit` exception will be its
      value.


.. attribute:: Greenlet.spawn_tree_locals

   A dictionary that is shared between all the greenlets in a "spawn
   tree", that is, a spawning greenlet and all its descendent
   greenlets. All children of the main (root) greenlet start their own
   spawn trees. Assign a new dictionary to this attribute on an
   instance of this class to create a new spawn tree (as far as locals
   are concerned).

   .. versionadded:: 1.3a2

.. attribute:: Greenlet.spawning_greenlet

   A weak-reference to the greenlet that was current when this object
   was created. Note that the :attr:`parent` attribute is always the
   hub.

   .. versionadded:: 1.3a2

.. attribute:: Greenlet.spawning_stack

   A lightweight :obj:`frame <types.FrameType>`-like object capturing the stack when
   this greenlet was created as well as the stack when the spawning
   greenlet was created (if applicable). This can be passed to
   :func:`traceback.print_stack`.

   .. versionadded:: 1.3a2

.. attribute:: Greenlet.spawning_stack_limit

   A class attribute specifying how many levels of the spawning stack
   will be kept. Specify a smaller number for higher performance,
   spawning greenlets, specify a larger value for improved debugging.

   .. versionadded:: 1.3a2


.. rubric:: Methods

.. automethod:: Greenlet.spawn
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
.. automethod:: Greenlet.__str__
.. automethod:: Greenlet.add_spawn_callback
.. automethod:: Greenlet.remove_spawn_callback


Raw greenlet Methods
====================

Being a greenlet__ subclass, :class:`Greenlet` also has `switch()
<switching>`_ and `throw() <throw>`_ methods. However, these should
not be used at the application level as they can very easily lead to
greenlets that are forever unscheduled. Prefer higher-level safe
classes, like :class:`Event <gevent.event.Event>` and :class:`Queue
<gevent.queue.Queue>`, instead.

__ https://greenlet.readthedocs.io/en/latest/#instantiation
.. _switching: https://greenlet.readthedocs.io/en/latest/#switching
.. _throw: https://greenlet.readthedocs.io/en/latest/#methods-and-attributes-of-greenlets

.. class:: greenlet.greenlet

    The base class from which `Greenlet` descends.


..  LocalWords:  Greenlet GreenletExit Greenlet's greenlet's
..  LocalWords:  automethod
