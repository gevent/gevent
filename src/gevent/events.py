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
    'IMemoryUsageThresholdExceeded',
    'MemoryUsageThresholdExceeded',
    'IMemoryUsageUnderThreshold',
    'MemoryUsageUnderThreshold',
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

class IMemoryUsageThresholdExceeded(Interface):
    """
    The event emitted when the memory usage threshold is exceeded.

    This event is emitted only while memory continues to grow
    above the threshold. Only if the condition or stabilized is corrected (memory
    usage drops) will the event be emitted in the future.

    This event is emitted in the monitor thread.
    """

    mem_usage = Attribute("The current process memory usage, in bytes.")
    max_allowed = Attribute("The maximum allowed memory usage, in bytes.")
    memory_info = Attribute("The tuple of memory usage stats return by psutil.")

class _AbstractMemoryEvent(object):

    def __init__(self, mem_usage, max_allowed, memory_info):
        self.mem_usage = mem_usage
        self.max_allowed = max_allowed
        self.memory_info = memory_info

    def __repr__(self):
        return "<%s used=%d max=%d details=%r>" % (
            self.__class__.__name__,
            self.mem_usage,
            self.max_allowed,
            self.memory_info,
        )

@implementer(IMemoryUsageThresholdExceeded)
class MemoryUsageThresholdExceeded(_AbstractMemoryEvent):
    """
    Implementation of `IMemoryUsageThresholdExceeded`.
    """


class IMemoryUsageUnderThreshold(Interface):
    """
    The event emitted when the memory usage drops below the
    threshold after having previously been above it.

    This event is emitted only the first time memory usage is detected
    to be below the threshold after having previously been above it.
    If memory usage climbs again, a `IMemoryUsageThresholdExceeded`
    event will be broadcast, and then this event could be broadcast again.

    This event is emitted in the monitor thread.
    """

    mem_usage = Attribute("The current process memory usage, in bytes.")
    max_allowed = Attribute("The maximum allowed memory usage, in bytes.")
    max_memory_usage = Attribute("The memory usage that caused the previous "
                                 "IMemoryUsageThresholdExceeded event.")
    memory_info = Attribute("The tuple of memory usage stats return by psutil.")


@implementer(IMemoryUsageUnderThreshold)
class MemoryUsageUnderThreshold(_AbstractMemoryEvent):
    """
    Implementation of `IMemoryUsageUnderThreshold`.
    """

    def __init__(self, mem_usage, max_allowed, memory_info, max_usage):
        super(MemoryUsageUnderThreshold, self).__init__(mem_usage, max_allowed, memory_info)
        self.max_memory_usage = max_usage
