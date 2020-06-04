# Copyright (c) 2020 gevent contributors.
"""
This module provides :class:`GeventSelector`, a high-level IO
multiplexing mechanism. This is aliased to :class:`DefaultSelector`.

This module provides the same API as the selectors defined in :mod:`selectors`.

On Python 2, this module is only available if the `selectors2
<https://pypi.org/project/selectors2/>`_ backport is installed.

.. versionadded:: NEXT
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math
try:
    import selectors as __selectors__
except ImportError:
    # Probably on Python 2. Do we have the backport?
    import selectors2 as __selectors__
    __target__ = 'selectors2'

from gevent._compat import iteritems
from gevent._util import copy_globals

from gevent.select import poll as Poll
from gevent.select import POLLIN
from gevent.select import POLLOUT

__implements__ = [
    'DefaultSelector',
]
__extra__ = [
    'GeventSelector',
]
__all__ = __implements__ + __extra__

__imports__ = copy_globals(
    __selectors__, globals(),
    names_to_ignore=__all__,
    # Copy __all__; __all__ is defined by selectors2 but not Python 3.
    dunder_names_to_keep=('__all__',)
)

_POLL_ALL = POLLIN | POLLOUT

EVENT_READ = __selectors__.EVENT_READ
EVENT_WRITE = __selectors__.EVENT_WRITE
_ALL_EVENTS = EVENT_READ | EVENT_WRITE
SelectorKey = __selectors__.SelectorKey

# In 3.4 and selectors2, BaseSelector is a concrete
# class that can be called. In 3.5 and later, it's an
# ABC, with the real implementation being
# passed to _BaseSelectorImpl.
_BaseSelectorImpl = getattr(
    __selectors__,
    '_BaseSelectorImpl',
    __selectors__.BaseSelector
)

class GeventSelector(_BaseSelectorImpl):
    """
    A selector implementation using gevent primitives.
    """

    def __init__(self):
        self._poll = Poll()
        self._poll._get_started_watchers = self._get_started_watchers
        # {fd: watcher}
        self._watchers = {}
        super(GeventSelector, self).__init__()

    def _get_started_watchers(self, watcher_cb):
        for fd, watcher in iteritems(self._watchers):
            watcher.start(watcher_cb, fd, pass_events=True)
        return list(self._watchers.values())

    @property
    def loop(self):
        return self._poll.loop

    def register(self, fileobj, events, data=None):
        key = _BaseSelectorImpl.register(self, fileobj, events, data)

        if events == _ALL_EVENTS:
            flags = _POLL_ALL
        elif events == EVENT_READ:
            flags = POLLIN
        else:
            flags = POLLOUT

        self._poll.register(key.fd, flags)

        loop = self.loop
        io = loop.io
        MAXPRI = loop.MAXPRI

        self._watchers[key.fd] = watcher = io(key.fd, self._poll.fds[key.fd])
        watcher.priority = MAXPRI
        return key

    def unregister(self, fileobj):
        key = _BaseSelectorImpl.unregister(self, fileobj)
        self._poll.unregister(key.fd)
        self._watchers.pop(key.fd)
        return key

    # XXX: Can we implement ``modify`` more efficiently than
    # ``unregister()``+``register()``? We could detect the no-change
    # case and do nothing; recent versions of the standard library
    # do that.

    def select(self, timeout=None):
        # In https://github.com/gevent/gevent/pull/1523/, it was
        # proposed to (essentially) keep the watchers started even
        # after the select() call returned *if* the watcher hadn't fired.
        # (If it fired, it was stopped). Watchers were started as soon as they
        # were registered.
        #
        # The goal was to minimize the amount of time spent adjusting the
        # underlying kernel (epoll) data structures as watchers are started and
        # stopped. Events were just collected continually in the background
        # in the hopes that they would be retrieved by a future call to
        # ```select()``. This method used an ``Event`` to communicate with
        # the background ongoing collection of results.
        #
        # That becomes a problem if the file descriptor is closed while the watcher
        # is still active. Certain backends will crash in that case.
        # However, the selectors documentation says that files must be
        # unregistered before closing, so that's theoretically not a concern
        # here.
        #
        # Also, stopping the watchers if they fired here was said to be
        # because "if we did not, someone could call, e.g., gevent.time.sleep and
        # any unconsumed bytes on our watched fd would prevent the process from
        # sleeping correctly." It's not clear to me (JAM) why that would be the case
        # only in the ``select`` method, and not after the watcher was started in
        # ``register()``. Actually, it's not clear why it would be a problem at any
        # point.

        # timeout > 0 : block seconds
        # timeout <= 0 : No blocking.
        # timeout = None: Block forever
        #
        # Meanwhile, for poll():
        # timeout None: block forever
        # timeout omitted: block forever
        # timeout < 0: block forever
        # timeout anything else: block that long in *milliseconds*

        if timeout is not None:
            if timeout <= 0:
                # Asked not to block.
                timeout = 0
            else:
                # Convert seconds to ms.
                # poll() has a resolution of 1 millisecond, round away from
                # zero to wait *at least* timeout seconds.
                timeout = math.ceil(timeout * 1e3)

        poll_events = self._poll.poll(timeout)
        result = []
        for fd, event in poll_events:
            key = self._key_from_fd(fd)
            if not key:
                continue

            events = 0
            if event & POLLOUT:
                events |= EVENT_WRITE
            if event & POLLIN:
                events |= EVENT_READ

            result.append((key, events & key.events))
        return result

    def close(self):
        self._poll = None # Nothing to do, just drop it
        for watcher in self._watchers.values() if self._watchers else ():
            watcher.stop()
            watcher.close()
        self._watchers = None
        _BaseSelectorImpl.close(self)


DefaultSelector = GeventSelector

def _gevent_do_monkey_patch(patch_request):
    aggressive = patch_request.patch_kwargs['aggressive']
    target_mod = patch_request.target_module

    patch_request.default_patch_items()

    import sys
    if 'selectors' not in sys.modules:
        # Py2: Make 'import selectors' work
        sys.modules['selectors'] = sys.modules[__name__]

    # Python 3 wants to use `select.select` as a member function,
    # leading to this error in selectors.py (because
    # gevent.select.select is not a builtin and doesn't get the
    # magic auto-static that they do):
    #
    #    r, w, _ = self._select(self._readers, self._writers, [], timeout)
    #    TypeError: select() takes from 3 to 4 positional arguments but 5 were given
    #
    # Note that this obviously only happens if selectors was
    # imported after we had patched select; but there is a code
    # path that leads to it being imported first (but now we've
    # patched select---so we can't compare them identically). It also doesn't
    # happen on Windows, because they define a normal method for _select, to work around
    # some weirdness in the handling of the third argument.
    #
    # The backport doesn't have that.
    orig_select_select = patch_request.get_original('select', 'select')
    assert target_mod.select is not orig_select_select
    selectors = __selectors__
    SelectSelector = selectors.SelectSelector
    if hasattr(SelectSelector, '_select') and SelectSelector._select in (
            target_mod.select, orig_select_select
    ):
        from gevent.select import select
        def _select(self, *args, **kwargs): # pylint:disable=unused-argument
            return select(*args, **kwargs)
        selectors.SelectSelector._select = _select
        _select._gevent_monkey = True # prove for test cases

    if aggressive:
        # If `selectors` had already been imported before we removed
        # select.epoll|kqueue|devpoll, these may have been defined in terms
        # of those functions. They'll fail at runtime.
        patch_request.remove_item(
            selectors,
            'EpollSelector',
            'KqueueSelector',
            'DevpollSelector',
        )
        selectors.DefaultSelector = DefaultSelector

    # Python 3.7 refactors the poll-like selectors to use a common
    # base class and capture a reference to select.poll, etc, at
    # import time. selectors tends to get imported early
    # (importing 'platform' does it: platform -> subprocess -> selectors),
    # so we need to clean that up.
    if hasattr(selectors, 'PollSelector') and hasattr(selectors.PollSelector, '_selector_cls'):
        selectors.PollSelector._selector_cls = Poll
