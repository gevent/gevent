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
from gevent._hub_local import get_hub_if_exists

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
    # With a few careful exceptions, instances of this object can only
    # be used from a single thread. The exception is that certain methods
    # may be used from multiple threads IFF:
    #
    # 1.  They are documented as safe for that purpose; AND
    # 2a. This object is compiled with Cython and thus is holding the GIL
    #     for the entire duration of the method; OR
    # 2b. A subclass ensures that a Python-level native thread lock is held
    #     for the duration of the method; this is necessary in pure-Python mode.
    #     The only known implementation of such
    #     a subclass is for Semaphore.
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
        # without initializing the hub. However, for multiple-thread safety, as soon
        # as a waiting method is entered, even if it won't have to wait, we
        # need to grab the hub and assign ownership. For that reason, if the hub
        # is present, we'll go ahead and take it.
        self.hub = hub if hub is not None else get_hub_if_exists()

    def linkcount(self):
        # For testing: how many objects are linked to this one?
        return len(self._links)

    def ready(self):
        # Instances must define this
        raise NotImplementedError

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

        if not self._links and self._notifier is not None and self._notifier.pending:
            # If we currently have one queued, but not running, de-queue it.
            # This will break a reference cycle.
            # (self._notifier -> self._notify_links -> self)
            # If it's actually running, though, (and we're here as a result of callbacks)
            # we don't want to change it; it needs to finish what its doing
            # so we don't attempt to start a fresh one or swap it out from underneath the
            # _notify_links method.
            self._notifier.stop()

    def _capture_hub(self, create):
        # Subclasses should call this as the first action from any
        # public method that could, in theory, block and switch
        # to the hub. This may release the GIL.
        if self.hub is None:
            # This next line might release the GIL.
            current_hub = get_hub() if create else get_hub_if_exists()
            if current_hub is None:
                return
            # We have the GIL again. Did anything change? If so,
            # we lost the race.
            if self.hub is None:
                self.hub = current_hub

    def _check_and_notify(self):
        # If this object is ready to be notified, begin the process.
        if self.ready() and self._links and not self._notifier:
            self._capture_hub(True) # Must create, we need it.
            self._notifier = self.hub.loop.run_callback(self._notify_links, [])

    def _notify_link_list(self, links):
        # The core of the _notify_links method to notify
        # links in order. Lets the ``links`` list be mutated,
        # and only notifies up to the last item in the list, in case
        # objects are added to it.
        only_while_ready = not self._notify_all
        final_link = links[-1]
        done = set() # of ids
        while links: # remember this can be mutated
            if only_while_ready and not self.ready():
                break

            link = links.pop(0) # Cython optimizes using list internals
            id_link = id(link)
            if id_link not in done:
                # XXX: JAM: What was I thinking? This doesn't make much sense,
                # there's a good chance `link` will be deallocated, and its id() will
                # be free to be reused.
                done.add(id_link)
                try:
                    self._drop_lock_for_switch_out()
                    try:
                        link(self)
                    finally:
                        self._acquire_lock_for_switch_in()
                except: # pylint:disable=bare-except
                    # We're running in the hub, errors must not escape.
                    self.hub.handle_error((link, self), *sys.exc_info())

            if link is final_link:
                break

    def _notify_links(self, arrived_while_waiting):
        # This method must hold the GIL, or be guarded with the lock that guards
        # this object. Thus, while we are notifying objects, an object from another
        # thread simply cannot arrive and mutate ``_links`` or ``arrived_while_waiting``

        # ``arrived_while_waiting`` is a list of greenlet.switch methods
        # to call. These were objects that called wait() while we were processing,
        # and which would have run *before* those that had actually waited
        # and blocked. Instead of returning True immediately, we add them to this
        # list so they wait their turn.

        # We release self._notifier here when done invoking links.
        # The object itself becomes false in a boolean way as soon
        # as this method returns.
        notifier = self._notifier
        # Early links are allowed to remove later links, and links
        # are allowed to add more links, thus we must not
        # make a copy of our the ``_links`` list, we must traverse it and
        # mutate in place.
        #
        # We were ready() at the time this callback was scheduled; we
        # may not be anymore, and that status may change during
        # callback processing. Some of our subclasses (Event) will
        # want to notify everyone who was registered when the status
        # became true that it was once true, even though it may not be
        # any more. In that case, we must not keep notifying anyone that's
        # newly added after that, even if we go ready again.
        try:
            self._notify_link_list(self._links)
            # Now, those that arrived after we had begun the notification
            # process. Follow the same rules, stop with those that are
            # added so far to prevent starvation.
            if arrived_while_waiting:
                self._notify_link_list(arrived_while_waiting)

                # Anything left needs to go back on the main list.
                self._links.extend(arrived_while_waiting)
        finally:
            # We should not have created a new notifier even if callbacks
            # released us because we loop through *all* of our links on the
            # same callback while self._notifier is still true.
            assert self._notifier is notifier
            self._notifier = None
            # TODO: Maybe we should intelligently reset self.hub to
            # free up thread affinity? In case of a pathological situation where
            # one object was used from one thread once & first,  but usually is
            # used by another thread.
        # Now we may be ready or not ready. If we're ready, which
        # could have happened during the last link we called, then we
        # must have more links than we started with. We need to schedule the
        # wakeup.
        self._check_and_notify()

    def __unlink_all(self, obj):
        if obj is None:
            return

        self.unlink(obj)
        if self._notifier is not None and self._notifier.args:
            try:
                self._notifier.args[0].remove(obj)
            except ValueError:
                pass

    def __wait_to_be_notified(self, rawlink): # pylint:disable=too-many-branches
        # We've got to watch where we could potentially release the GIL.
        # Decisions we make based an the state of this object must be in blocks
        # that cannot release the GIL.
        resume_this_greenlet = None
        watcher = None
        current_hub = get_hub()
        send = None

        while 1:
            my_hub = self.hub
            if my_hub is current_hub:
                break

            # We're owned by another hub.
            if my_hub.dead: # dead is a property, this could have released the GIL.
                # We have the GIL back. Did anything change?
                if my_hub is not self.hub:
                    continue # start over.
                # The other hub is dead, so we can take ownership.
                self.hub = current_hub
                break
            # Some other hub owns this object. We must ask it to wake us
            # up. We can't use a Python-level ``Lock`` because
            # (1) it doesn't support a timeout on all platforms; and
            # (2) we don't want to block this hub from running. So we need to
            # do so in a way that cooperates with *two* hubs. That's what an
            # async watcher is built for.
            #
            # Allocating and starting the watcher *could* release the GIL.
            # with the libev corcext, allocating won't, but starting briefly will.
            # With other backends, allocating might, and starting might also.
            # So...XXX: Race condition here, tiny though it may be.
            watcher = current_hub.loop.async_()
            send = watcher.send_ignoring_arg
            if rawlink:
                # Make direct calls to self.rawlink, the most common case,
                # so cython can more easily optimize.
                self.rawlink(send)
            else:
                self._notifier.args[0].append(send)

            watcher.start(getcurrent().switch, self) # pylint:disable=undefined-variable
            break

        if self.hub is current_hub:
            resume_this_greenlet = getcurrent().switch # pylint:disable=undefined-variable
            if rawlink:
                self.rawlink(resume_this_greenlet)
            else:
                self._notifier.args[0].append(resume_this_greenlet)
        try:
            self._drop_lock_for_switch_out()
            result = current_hub.switch() # Probably releases
            # If we got here, we were automatically unlinked already.
            resume_this_greenlet = None
            if result is not self: # pragma: no cover
                raise InvalidSwitchError(
                    'Invalid switch into %s.wait(): %r' % (
                        self.__class__.__name__,
                        result,
                    )
                )
        finally:
            self._acquire_lock_for_switch_in()
            self.__unlink_all(resume_this_greenlet)
            self.__unlink_all(send)
            if watcher is not None:
                watcher.stop()
                watcher.close()

    def _acquire_lock_for_switch_in(self):
        return

    def _drop_lock_for_switch_out(self):
        return

    def _wait_core(self, timeout, catch=Timeout):
        """
        The core of the wait implementation, handling switching and
        linking.

        This method is safe to call from multiple threads; it must be holding
        the GIL for the entire duration, or be protected by a Python-level
        lock for that to be true.

        ``self.hub`` must be initialized before entering this method.
        The hub that is set is considered the owner and cannot be changed.

        If *catch* is set to ``()``, a timeout that elapses will be
        allowed to be raised.

        :return: A true value if the wait succeeded without timing out.
          That is, a true return value means we were notified and control
          resumed in this greenlet.
        """
        with Timeout._start_new_or_dummy(timeout) as timer: # Might release
            try:
                self.__wait_to_be_notified(True) # Use rawlink()
                return True
            except catch as ex:
                if ex is not timer:
                    raise
                # test_set_and_clear and test_timeout in test_threading
                # rely on the exact return values, not just truthish-ness
                return False

    def _wait_return_value(self, waited, wait_success):
        # pylint:disable=unused-argument
        # Subclasses should override this to return a value from _wait.
        # By default we return None.
        return None # pragma: no cover all extent subclasses override

    def _wait(self, timeout=None):
        """
        This method is safe to call from multiple threads, providing
        the conditions laid out in the class documentation are met.
        """
        # Watch where we could potentially release the GIL.
        self._capture_hub(True) # Must create, we must have an owner. Might release

        if self.ready(): # *might* release, if overridden in Python.
            result = self._wait_return_value(False, False) # pylint:disable=assignment-from-none
            if self._notifier:
                # We're already notifying waiters; one of them must have run
                # and switched to this greenlet, which arrived here. Alternately,
                # we could be in a separate thread (but we're holding the GIL/object lock)
                self.__wait_to_be_notified(False) # Use self._notifier.args[0] instead of self.rawlink

            return result

        gotit = self._wait_core(timeout)
        return self._wait_return_value(True, gotit)

def _init():
    greenlet_init() # pylint:disable=undefined-variable

_init()


from gevent._util import import_c_accel
import_c_accel(globals(), 'gevent.__abstract_linkable')
