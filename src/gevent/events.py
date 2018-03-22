# -*- coding: utf-8 -*-
# Copyright 2018 gevent. See LICENSE for details.
"""
Publish/subscribe event infrastructure.

When certain "interesting" things happen during the lifetime of the
process, gevent will "publish" an event (an object). That event is
delivered to interested "subscribers" (functions that take one
parameter, the event object).

Higher level frameworks may take this foundation and build richer
models on it.

If :mod:`zope.event` is installed, then it will be used to provide the
functionality of `notify` and `subscribers`. See
:mod:`zope.event.classhandler` for a simple class-based approach to
subscribing to a filtered list of events, and see `zope.component
<https://zopecomponent.readthedocs.io/en/latest/event.html>`_ for a
much higher-level, flexible system. If you are using one of these systems,
you generally will not want to directly modify `subscribers`.

.. versionadded:: 1.3b1
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


__all__ = [
    'subscribers',
    'IEventLoopBlocked',
    'EventLoopBlocked',
]

try:
    from zope.event import subscribers
    from zope.event import notify
except ImportError:
    #: Applications may register for notification of events by appending a
    #: callable to the ``subscribers`` list.
    #:
    #: Each subscriber takes a single argument, which is the event object
    #: being published.
    #:
    #: Exceptions raised by subscribers will be propagated *without* running
    #: any remaining subscribers.
    subscribers = []

    def notify(event):
        """
        Notify all subscribers of ``event``.
        """
        for subscriber in subscribers:
            subscriber(event)

notify = notify # export

try:
    from zope.interface import Interface
    from zope.interface import implementer
    from zope.interface import Attribute
except ImportError:
    class Interface(object):
        pass
    def implementer(_iface):
        def dec(c):
            return c
        return dec

    def Attribute(s):
        return s


class IEventLoopBlocked(Interface):
    """
    The event emitted when the event loop is blocked.

    This event is emitted in the monitor thread.
    """

    greenlet = Attribute("The greenlet that appeared to be blocking the loop.")
    blocking_time = Attribute("The approximate time in seconds the loop has been blocked.")
    info = Attribute("A sequence of string lines providing extra info.")

@implementer(IEventLoopBlocked)
class EventLoopBlocked(object):
    """
    The event emitted when the event loop is blocked.

    Implements `IEventLoopBlocked`.
    """

    def __init__(self, greenlet, blocking_time, info):
        self.greenlet = greenlet
        self.blocking_time = blocking_time
        self.info = info
