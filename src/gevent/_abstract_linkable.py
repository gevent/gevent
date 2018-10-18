# -*- coding: utf-8 -*-
# cython: auto_pickle=False,embedsignature=True,always_allow_keywords=False
"""
Internal module, support for the linkable protocol for "event" like objects.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

from gevent._hub_local import get_hub_noargs as get_hub

from gevent.exceptions import InvalidSwitchError
from gevent.timeout import Timeout

locals()['getcurrent'] = __import__('greenlet').getcurrent
locals()['greenlet_init'] = lambda: None

__all__ = [
    'AbstractLinkable',
]

class AbstractLinkable(object):
    # Encapsulates the standard parts of the linking and notifying
    # protocol common to both repeatable events (Event, Semaphore) and
    # one-time events (AsyncResult).

    __slots__ = ('_links', 'hub', '_notifier', '_notify_all', '__weakref__')

    def __init__(self):
        # Before this implementation, AsyncResult and Semaphore
        # maintained the order of notifications, but Event did not.

        # In gevent 1.3, before Semaphore extended this class,
        # that was changed to not maintain the order. It was done because
        # Event guaranteed to only call callbacks once (a set) but
        # AsyncResult had no such guarantees.

        # Semaphore likes to maintain order of callbacks, though,
        # so when it was added we went back to a list implementation
        # for storing callbacks. But we want to preserve the unique callback
        # property, so we manually check.

        # We generally don't expect to have so many waiters (for any of those
        # objects) that testing membership and removing is a bottleneck.

        # In PyPy 2.6.1 with Cython 0.23, `cdef public` or `cdef
        # readonly` or simply `cdef` attributes of type `object` can appear to leak if
        # a Python subclass is used (this is visible simply
        # instantiating this subclass if _links=[]). Our _links and
        # _notifier are such attributes, and gevent.thread subclasses
        # this class. Thus, we carefully manage the lifetime of the
        # objects we put in these attributes so that, in the normal
        # case of a semaphore used correctly (deallocated when it's not
        # locked and no one is waiting), the leak goes away (because
        # these objects are back to None). This can also be solved on PyPy
        # by simply not declaring these objects in the pxd file, but that doesn't work for
        # CPython ("No attribute...")
        # See https://github.com/gevent/gevent/issues/660
        self._links = None
        # we don't want to do get_hub() here to allow defining module-level locks
        # without initializing the hub
        self.hub = None
        self._notifier = None
        # This is conceptually a class attribute, defined here for ease of access in
        # cython. If it's true, when notifiers fire, all existing callbacks are called.
        # If its false, we only call callbacks as long as ready() returns true.
        self._notify_all = True

    def linkcount(self):
        # For testing: how many objects are linked to this one?
        return len(self._links) if self._links is not None else 0

    def ready(self):
        # Instances must define this
        raise NotImplementedError

    def _check_and_notify(self):
        # If this object is ready to be notified, begin the process.
        if self.ready():
            if self._links and not self._notifier:
                if self.hub is None:
                    self.hub = get_hub()
                self._notifier = self.hub.loop.run_callback(self._notify_links)

    def rawlink(self, callback):
        """
        Register a callback to call when this object is ready.

        *callback* will be called in the :class:`Hub <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        if self._links is None:
            self._links = [callback]
        else:
            self._links.append(callback)

        self._check_and_notify()

    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        if self._links is not None:
            try:
                self._links.remove(callback)
            except ValueError:
                pass
            if not self._links:
                self._links = None
            # TODO: Cancel a notifier if there are no links?

    def _notify_links(self):
        # Actually call the notification callbacks. Those callbacks in todo that are
        # still in _links are called. This method is careful to avoid iterating
        # over self._links, because links could be added or removed while this
        # method runs. Only links present when this method begins running
        # will be called; if a callback adds a new link, it will not run
        # until the next time notify_links is activated

        notifier = self._notifier
        # We don't need to capture self._links as todo when establishing
        # this callback; any links removed between now and then are handled
        # by the `if` below; any links added are also grabbed; note that if
        # unlink() was called while we were waiting for the notifier to run,
        # self._links could have gone to None.
        todo = list(self._links) if self._links is not None else []
        try:
            for link in todo:
                # check that link was not notified yet and was not removed by the client
                # We have to do this here, and not as part of the 'for' statement because
                # a previous link(self) call might have altered self._links
                if not self._notify_all and not self.ready():
                    break
                if link in self._links:
                    try:
                        link(self)
                    except: # pylint:disable=bare-except
                        self.hub.handle_error((link, self), *sys.exc_info())
                    if getattr(link, 'auto_unlink', None):
                        # This attribute can avoid having to keep a reference to the function
                        # *in* the function, which is a cycle
                        self.unlink(link)
        finally:
            # save a tiny bit of memory by letting _notifier be collected
            # bool(self._notifier) would turn to False as soon as we exit this
            # method anyway.
            del todo
            # We should not have created a new notifier even if callbacks
            # released us because we loop through *all* of our links on the
            # same callback while self._notifier is still true.
            assert self._notifier is notifier
            self._notifier = None

    def _wait_core(self, timeout, catch=Timeout):
        # The core of the wait implementation, handling
        # switching and linking. If *catch* is set to (),
        # a timeout that elapses will be allowed to be raised.
        # Returns a true value if the wait succeeded without timing out.
        switch = getcurrent().switch # pylint:disable=undefined-variable
        self.rawlink(switch)
        try:
            with Timeout._start_new_or_dummy(timeout) as timer:
                try:
                    if self.hub is None:
                        self.hub = get_hub()
                    result = self.hub.switch()
                    if result is not self: # pragma: no cover
                        raise InvalidSwitchError('Invalid switch into Event.wait(): %r' % (result, ))
                    return True
                except catch as ex:
                    if ex is not timer:
                        raise
                    # test_set_and_clear and test_timeout in test_threading
                    # rely on the exact return values, not just truthish-ness
                    return False
        finally:
            self.unlink(switch)

    def _wait_return_value(self, waited, wait_success):
        # pylint:disable=unused-argument
        return None

    def _wait(self, timeout=None):
        if self.ready():
            return self._wait_return_value(False, False)

        gotit = self._wait_core(timeout)
        return self._wait_return_value(True, gotit)

def _init():
    greenlet_init() # pylint:disable=undefined-variable

_init()


from gevent._util import import_c_accel
import_c_accel(globals(), 'gevent.__abstract_linkable')
