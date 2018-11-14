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

    __slots__ = ('hub', '_links', '_notifier', '_notify_all', '__weakref__')

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
        self._links = set()
        self._notifier = None
        # This is conceptually a class attribute, defined here for ease of access in
        # cython. If it's true, when notifiers fire, all existing callbacks are called.
        # If its false, we only call callbacks as long as ready() returns true.
        self._notify_all = True
        # we don't want to do get_hub() here to allow defining module-level objects
        # without initializing the hub
        self.hub = None

    def linkcount(self):
        # For testing: how many objects are linked to this one?
        return len(self._links)

    def ready(self):
        # Instances must define this
        raise NotImplementedError

    def _check_and_notify(self):
        # If this object is ready to be notified, begin the process.
        if self.ready() and self._links and not self._notifier:
            if self.hub is None:
                self.hub = get_hub()

            self._notifier = self.hub.loop.run_callback(self._notify_links)

    def rawlink(self, callback):
        """
        Register a callback to call when this object is ready.

        *callback* will be called in the :class:`Hub
        <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))

        self._links.add(callback)
        self._check_and_notify()

    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        self._links.discard(callback)

        if not self._links and self._notifier is not None:
            # If we currently have one queued, de-queue it.
            # This will break a reference cycle.
            # (self._notifier -> self._notify_links -> self)
            # But we can't set it to None in case it was actually running.
            self._notifier.stop()


    def _notify_links(self):
        # We release self._notifier here. We are called by it
        # at the end of the loop, and it is now false in a boolean way (as soon
        # as this method returns).
        notifier = self._notifier
        # We were ready() at the time this callback was scheduled;
        # we may not be anymore, and that status may change during
        # callback processing. Some of our subclasses will want to
        # notify everyone that the status was once true, even though not it
        # may not be anymore.
        todo = set(self._links)
        try:
            for link in todo:
                if not self._notify_all and not self.ready():
                    break

                if link not in self._links:
                    # Been removed already by some previous link. OK, fine.
                    continue
                try:
                    link(self)
                except: # pylint:disable=bare-except
                    # We're running in the hub, so getcurrent() returns
                    # a hub.
                    self.hub.handle_error((link, self), *sys.exc_info()) # pylint:disable=undefined-variable
                finally:
                    if getattr(link, 'auto_unlink', None):
                        # This attribute can avoid having to keep a reference to the function
                        # *in* the function, which is a cycle
                        self.unlink(link)
        finally:
            # We should not have created a new notifier even if callbacks
            # released us because we loop through *all* of our links on the
            # same callback while self._notifier is still true.
            assert self._notifier is notifier
            self._notifier = None

        # Our set of active links changed, and we were told to stop on the first
        # time we went unready. See if we're ready, and if so, go around
        # again.
        if not self._notify_all and todo != self._links:
            self._check_and_notify()

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
        # Subclasses should override this to return a value from _wait.
        # By default we return None.
        return None # pragma: no cover all extent subclasses override

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
