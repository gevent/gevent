"""Hide this thread's asyncio loop from other greenlets.

CPython 3.13.12 and 3.14.3 changed ``asyncio.futures._chain_future`` so that
a completion on the loop's OS thread calls ``loop.call_soon`` instead of
``call_soon_threadsafe``. Monkey-patched executor workers are greenlets on
that same thread, so ``_get_running_loop()`` still returns the loop and the
selector is never woken. Record which greenlet entered the loop and report
no running loop from any other greenlet.
"""

from __future__ import absolute_import

import sys

_patched = False


def patch_asyncio_running_loop():
    global _patched
    if _patched or sys.version_info < (3, 7):
        return

    try:
        from asyncio import events
    except ImportError:
        return

    from greenlet import getcurrent

    original_get = events._get_running_loop
    original_set = events._set_running_loop

    def _get_running_loop():
        loop = original_get()
        if loop is None:
            return None
        owner = getattr(loop, '_gevent_running_greenlet', None)
        if owner is not None and owner is not getcurrent():
            return None
        return loop

    def _set_running_loop(loop):
        if loop is not None:
            try:
                loop._gevent_running_greenlet = getcurrent()
            except (AttributeError, TypeError):
                pass
        original_set(loop)

    events._get_running_loop = _get_running_loop
    events._set_running_loop = _set_running_loop
    _patched = True
