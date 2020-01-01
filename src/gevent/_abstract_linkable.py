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
    #
    # TODO: As of gevent 1.5, we use the same datastructures and almost
    # the same algorithm as Greenlet. See about unifying them more.

    __slots__ = (
        'hub',
        '_links',
        '_notifier',
        '_notify_all',
        '__weakref__'
    )

    def __init__(self, hub=None):
        # Before this implementation, AsyncResult and Semaphore
        # maintained the order of notifications, but Event did not.

        # In gevent 1.3, before Semaphore extended this class, that
        # was changed to not maintain the order. It was done because
        # Event guaranteed to only call callbacks once (a set) but
        # AsyncResult had no such guarantees. When Semaphore was
        # changed to extend this class, it lost its ordering
        # guarantees. Unfortunately, that made it unfair. There are
        # rare cases that this can starve a greenlet
        # (https://github.com/gevent/gevent/issues/1487) and maybe
        # even lead to deadlock (not tested).

        # So in gevent 1.5 we go back to maintaining order. But it's
        # still important not to make duplicate calls, and it's also
        # important to avoid O(n^2) behaviour that can result from
        # naive use of a simple list due to the need to handle removed
        # links in the _notify_links loop. Cython has special support for
        # built-in sets, lists, and dicts, but not ordereddict. Rather than
        # use two data structures, or a dict({link: order}), we simply use a
        # list and remove objects as we go, keeping track of them so as not to
        # have duplicates called. This makes `unlink` O(n), but we can avoid
        # calling it in the common case in _wait_core (even so, the number of
        # waiters should usually be pretty small)
        self._links = []
        self._notifier = None
        # This is conceptually a class attribute, defined here for ease of access in
        # cython. If it's true, when notifiers fire, all existing callbacks are called.
        # If its false, we only call callbacks as long as ready() returns true.
        self._notify_all = True
        # we don't want to do get_hub() here to allow defining module-level objects
        # without initializing the hub
        self.hub = hub

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
        self._links.append(callback)
        self._check_and_notify()

    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        try:
            self._links.remove(callback)
        except ValueError:
            pass

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
        # Early links are allowed to remove later links, and links
        # are allowed to add more links.
        #
        # We were ready() at the time this callback was scheduled; we
        # may not be anymore, and that status may change during
        # callback processing. Some of our subclasses (Event) will
        # want to notify everyone who was registered when the status
        # became true that it was once true, even though it may not be
        # anymore. In that case, we must not keep notifying anyone that's
        # newly added after that, even if we go ready again.
        final_link = self._links[-1]
        only_while_ready = not self._notify_all
        done = set() # of ids
        try:
            while self._links: # remember this can be mutated
                if only_while_ready and not self.ready():
                    break

                link = self._links.pop(0) # Cython optimizes using list internals

                id_link = id(link)
                if id_link not in done:
                    # XXX: JAM: What was I thinking? This doesn't make much sense,
                    # there's a good chance `link` will be deallocated, and its id() will
                    # be free to be reused.
                    done.add(id_link)
                    try:
                        link(self)
                    except: # pylint:disable=bare-except
                        # We're running in the hub, errors must not escape.
                        self.hub.handle_error((link, self), *sys.exc_info())

                if link is final_link:
                    break
        finally:
            # We should not have created a new notifier even if callbacks
            # released us because we loop through *all* of our links on the
            # same callback while self._notifier is still true.
            assert self._notifier is notifier
            self._notifier = None

        # Now we may be ready or not ready. If we're ready, which
        # could have happened during the last link we called, then we
        # must have more links than we started with. We need to schedule the
        # wakeup.
        self._check_and_notify()

    def _wait_core(self, timeout, catch=Timeout):
        # The core of the wait implementation, handling
        # switching and linking. If *catch* is set to (),
        # a timeout that elapses will be allowed to be raised.
        # Returns a true value if the wait succeeded without timing out.
        switch = getcurrent().switch # pylint:disable=undefined-variable
        self.rawlink(switch)
        with Timeout._start_new_or_dummy(timeout) as timer:
            try:
                if self.hub is None:
                    self.hub = get_hub()
                result = self.hub.switch()
                if result is not self: # pragma: no cover
                    raise InvalidSwitchError('Invalid switch into Event.wait(): %r' % (result, ))
                # If we got here, we were automatically unlinked already.
                return True
            except catch as ex:
                self.unlink(switch)
                if ex is not timer:
                    raise
                # test_set_and_clear and test_timeout in test_threading
                # rely on the exact return values, not just truthish-ness
                return False
            except:
                self.unlink(switch)
                raise

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
