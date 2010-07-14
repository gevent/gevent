:mod:`gevent.event` -- Notifications of multiple listeners
==========================================================

.. module:: gevent.event

.. autoclass:: gevent.event.Event
    :members: set, clear, wait, rawlink, unlink

    .. method:: is_set()
                isSet()

       Return true if and only if the internal flag is true.


.. autoclass:: gevent.event.AsyncResult
    :members:
    :undoc-members:

    .. attribute:: value

       Holds the value passed to :meth:`set` if :meth:`set` was called. Otherwise ``None``.

