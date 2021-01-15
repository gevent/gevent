=============================================
 ``gevent.hub`` - The Event Loop and the Hub
=============================================

.. module:: gevent.hub

The hub is a special greenlet created automatically to run the event loop.

The current hub can be retrieved with `get_hub`.

.. autofunction:: get_hub


.. autoclass:: Hub
    :members:

    .. automethod:: wait
    .. automethod:: cancel_wait

    .. attribute:: loop
       the event loop object (`ILoop`) associated with this hub and thus
       this native thread.


The Event Loop
==============

The current event loop can be obtained with ``get_hub().loop``.
All implementations of the loop provide a common minimum interface.

.. autointerface:: gevent._interfaces.ILoop
.. autointerface:: gevent._interfaces.IWatcher
.. autointerface:: gevent._interfaces.ICallback

Utilities
=========

.. autoclass:: Waiter

Exceptions
==========

.. autoclass:: LoopExit


The following exceptions *are not* expected to be thrown and *are not*
meant to be caught; if they are raised to user code it is generally a
serious programming error or a bug in gevent, greenlet, or its event
loop implementation. They are presented here for documentation
purposes only.

.. autoclass:: gevent.exceptions.ConcurrentObjectUseError
.. autoclass:: gevent.exceptions.BlockingSwitchOutError
.. autoclass:: gevent.exceptions.InvalidSwitchError
