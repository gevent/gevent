# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.
"""
Low-level utilities.
"""

from __future__ import absolute_import, print_function, division

import functools

__all__ = [
    'wrap_errors',
    'format_run_info',
]


class wrap_errors(object):
    """
    Helper to make function return an exception, rather than raise it.

    Because every exception that is unhandled by greenlet will be logged,
    it is desirable to prevent non-error exceptions from leaving a greenlet.
    This can done with a simple ``try/except`` construct::

        def wrapped_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (TypeError, ValueError, AttributeError) as ex:
                return ex

    This class provides a shortcut to write that in one line::

        wrapped_func = wrap_errors((TypeError, ValueError, AttributeError), func)

    It also preserves ``__str__`` and ``__repr__`` of the original function.
    """
    # QQQ could also support using wrap_errors as a decorator

    def __init__(self, errors, func):
        """
        Calling this makes a new function from *func*, such that it catches *errors* (an
        :exc:`BaseException` subclass, or a tuple of :exc:`BaseException` subclasses) and
        return it as a value.
        """
        self.__errors = errors
        self.__func = func
        # Set __doc__, __wrapped__, etc, especially useful on Python 3.
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        func = self.__func
        try:
            return func(*args, **kwargs)
        except self.__errors as ex:
            return ex

    def __str__(self):
        return str(self.__func)

    def __repr__(self):
        return repr(self.__func)

    def __getattr__(self, name):
        return getattr(self.__func, name)

def format_run_info():
    """
    Request information about the running threads of the current process.

    This is a debugging utility. Its output has no guarantees other than being
    intended for human consumption.

    :return: A sequence of text lines detailing the stacks of running
            threads and greenlets. (One greenlet will duplicate one thread,
            the current thread and greenlet.) Extra information about
            :class:`gevent.greenlet.Greenlet` object will also be returned.

    .. versionadded:: 1.3a1
    .. versionchanged:: 1.3a2
       Renamed from ``dump_stacks`` to reflect the fact that this
       prints additional information about greenlets, including their
       spawning stack, parent, and any spawn tree locals.
    """

    lines = []

    _format_thread_info(lines)
    _format_greenlet_info(lines)
    return lines

def _format_thread_info(lines):
    import threading
    import sys
    import traceback

    threads = {th.ident: th.name for th in threading.enumerate()}

    lines.append('*' * 80)
    lines.append('* Threads')

    thread = None
    frame = None
    for thread, frame in sys._current_frames().items():
        lines.append("*" * 80)
        lines.append('Thread 0x%x (%s)\n' % (thread, threads.get(thread)))
        lines.append(''.join(traceback.format_stack(frame)))

    # We may have captured our own frame, creating a reference
    # cycle, so clear it out.
    del thread
    del frame
    del lines
    del threads

def _format_greenlet_info(lines):
    from greenlet import greenlet
    import pprint
    import traceback
    import gc

    def _noop():
        return None

    # Use the gc module to inspect all objects to find the greenlets
    # since there isn't a global registry
    lines.append('*' * 80)
    lines.append('* Greenlets')
    seen_locals = set() # {id}
    for ob in gc.get_objects():
        if not isinstance(ob, greenlet):
            continue
        if not ob:
            continue  # not running anymore or not started
        lines.append('*' * 80)
        lines.append('Greenlet %s\n' % ob)
        lines.append(''.join(traceback.format_stack(ob.gr_frame)))
        spawning_stack = getattr(ob, 'spawning_stack', None)
        if spawning_stack:
            lines.append("Spawned at: ")
            lines.append(''.join(traceback.format_stack(spawning_stack)))
        parent = getattr(ob, 'spawning_greenlet', _noop)()
        if parent is not None:
            lines.append("Parent greenlet: %s\n" % (parent,))
        spawn_tree_locals = getattr(ob, 'spawn_tree_locals', None)
        if spawn_tree_locals and id(spawn_tree_locals) not in seen_locals:
            seen_locals.add(id(spawn_tree_locals))
            lines.append("Spawn Tree Locals:\n")
            lines.append(pprint.pformat(spawn_tree_locals))


    del lines

dump_stacks = format_run_info
