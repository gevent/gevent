# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.
"""
Low-level utilities.
"""

from __future__ import absolute_import, print_function, division

import gc
import functools
import pprint
import traceback

from greenlet import getcurrent
from greenlet import greenlet as RawGreenlet

from gevent.local import all_local_dicts_for_greenlet

__all__ = [
    'wrap_errors',
    'format_run_info',
    'GreenletTree',
]

def _noop():
    return None

def _ready():
    return False

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
       spawning stack, parent, locals, and any spawn tree locals.
    """

    lines = []

    _format_thread_info(lines)
    _format_greenlet_info(lines)
    return lines

def _format_thread_info(lines):
    import threading
    import sys

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
    # Use the gc module to inspect all objects to find the greenlets
    # since there isn't a global registry
    lines.append('*' * 80)
    lines.append('* Greenlets')
    lines.append('*' * 80)
    for tree in GreenletTree.forest():
        lines.extend(tree.format_lines(details=True))

    del lines

dump_stacks = format_run_info

def _line(f):
    @functools.wraps(f)
    def w(self, *args, **kwargs):
        r = f(self, *args, **kwargs)
        self.lines.append(r)

    return w

class _TreeFormatter(object):
    UP_AND_RIGHT = '+'
    HORIZONTAL = '-'
    VERTICAL = '|'
    VERTICAL_AND_RIGHT = '+'
    DATA = ':'

    label_space = 1
    horiz_width = 3
    indent = 1

    def __init__(self, details, depth=0):
        self.lines = []
        self.depth = depth
        self.details = details
        if not details:
            self.child_data = lambda *args, **kwargs: None

    def deeper(self):
        return type(self)(self.details, self.depth + 1)

    @_line
    def node_label(self, text):
        return text

    @_line
    def child_head(self, label, right=VERTICAL_AND_RIGHT):
        return (
            ' ' * self.indent
            + right
            + self.HORIZONTAL * self.horiz_width
            + ' ' * self.label_space
            + label
        )

    def last_child_head(self, label):
        return self.child_head(label, self.UP_AND_RIGHT)

    @_line
    def child_tail(self, line, vertical=VERTICAL):
        return (
            ' ' * self.indent
            + vertical
            + ' ' * self.horiz_width
            + line
        )

    def last_child_tail(self, line):
        return self.child_tail(line, vertical=' ' * len(self.VERTICAL))

    @_line
    def child_data(self, data, data_marker=DATA): # pylint:disable=method-hidden
        return ((
            ' ' * self.indent
            + (data_marker if not self.depth else ' ')
            + ' ' * self.horiz_width
            + ' ' * self.label_space
            + data
        ),)

    def last_child_data(self, data):
        return self.child_data(data, ' ')

    def child_multidata(self, data):
        # Remove embedded newlines
        for l in data.splitlines():
            self.child_data(l)


class GreenletTree(object):
    """
    Represents a tree of greenlets.

    In gevent, the *parent* of a greenlet is usually the hub, so this
    tree is primarily arganized along the *spawning_greenlet* dimension.

    This object has a small str form showing this hierarchy. The `format`
    method can output more details. The exact output is unspecified but is
    intended to be human readable.

    Use the `forest` method to get the root greenlet trees for
    all threads, and the `current_tree` to get the root greenlet tree for
    the current thread.
    """

    #: The greenlet this tree represents.
    greenlet = None


    def __init__(self, greenlet):
        self.greenlet = greenlet
        self.child_trees = []

    def add_child(self, tree):
        if tree is self:
            return
        self.child_trees.append(tree)

    @property
    def root(self):
        return self.greenlet.parent is None

    def __getattr__(self, name):
        return getattr(self.greenlet, name)

    def format_lines(self, details=True):
        """
        Return a sequence of lines for the greenlet tree.

        :keyword bool details: If true (the default),
            then include more informative details in the output.
        """
        if not isinstance(details, dict):
            if not details:
                details = {}
            else:
                details = {'stacks': True, 'locals': True}
        tree = _TreeFormatter(details, depth=0)
        lines = [l[0] if isinstance(l, tuple) else l
                 for l in self._render(tree)]
        return lines

    def format(self, details=True):
        """
        Like `format_lines` but returns a string.
        """
        lines = self.format_lines(details)
        return '\n'.join(lines)

    def __str__(self):
        return self.format(False)

    @staticmethod
    def __render_tb(tree, label, frame):
        tree.child_data(label)
        tb = ''.join(traceback.format_stack(frame))
        tree.child_multidata(tb)

    def __render_locals(self, tree):
        gr_locals = all_local_dicts_for_greenlet(self.greenlet)
        if gr_locals:
            tree.child_data("Greenlet Locals:")
            for (kind, idl), vals in gr_locals:
                tree.child_data("  Local %s at %s" % (kind, hex(idl)))
                tree.child_multidata("    " + pprint.pformat(vals))

    def _render(self, tree):
        label = repr(self.greenlet)
        if not self.greenlet: # Not running or dead
            # raw greenlets do not have ready
            if getattr(self.greenlet, 'ready', _ready)():
                label += '; finished'
                if self.greenlet.value is not None:
                    label += ' with value ' + repr(self.greenlet.value)[:30]
                elif getattr(self.greenlet, 'exception', None) is not None:
                    label += ' with exception ' + repr(self.greenlet.exception)
            else:
                label += '; not running'
        tree.node_label(label)

        if self.greenlet.parent is not None:
            tree.child_data('Parent: ' + repr(self.greenlet.parent))

        if self.greenlet and tree.details and tree.details['stacks']:
            self.__render_tb(tree, 'Running:', self.greenlet.gr_frame)


        spawning_stack = getattr(self.greenlet, 'spawning_stack', None)
        if spawning_stack and tree.details and tree.details['stacks']:
            self.__render_tb(tree, 'Spawned at:', spawning_stack)

        spawning_parent = getattr(self.greenlet, 'spawning_greenlet', _noop)()
        tree_locals = getattr(self.greenlet, 'spawn_tree_locals', None)
        if tree_locals and tree_locals is not getattr(spawning_parent, 'spawn_tree_locals', None):
            tree.child_data('Spawn Tree Locals')
            tree.child_multidata(pprint.pformat(tree_locals))

        self.__render_locals(tree)
        self.__render_children(tree)
        return tree.lines

    def __render_children(self, tree):
        children = sorted(self.child_trees,
                          key=lambda c: (
                              # raw greenlets first
                              getattr(c, 'minimal_ident', -1),
                              # running greenlets first
                              getattr(c, 'ready', _ready)(),
                              id(c.parent)))
        for n, child in enumerate(children):
            child_tree = child._render(tree.deeper())

            head = tree.child_head
            tail = tree.child_tail
            data = tree.child_data

            if n == len(children) - 1:
                # last child does not get the line drawn
                head = tree.last_child_head
                tail = tree.last_child_tail
                data = tree.last_child_data

            head(child_tree.pop(0))
            for child_data in child_tree:
                if isinstance(child_data, tuple):
                    data(child_data[0])
                else:
                    tail(child_data)

        return tree.lines


    @staticmethod
    def _root_greenlet(greenlet):
        while greenlet.parent is not None:
            greenlet = greenlet.parent
        return greenlet

    @classmethod
    def _forest(cls):
        main_greenlet = cls._root_greenlet(getcurrent())

        trees = {}
        roots = {}
        current_tree = roots[main_greenlet] = trees[main_greenlet] = cls(main_greenlet)



        for ob in gc.get_objects():
            if not isinstance(ob, RawGreenlet):
                continue

            spawn_parent = getattr(ob, 'spawning_greenlet', _noop)()

            if spawn_parent is None:
                root = cls._root_greenlet(ob)
                try:
                    tree = roots[root]
                except KeyError: # pragma: no cover
                    tree = GreenletTree(root)
                    roots[root] = trees[root] = tree
            else:
                try:
                    tree = trees[spawn_parent]
                except KeyError: # pragma: no cover
                    tree = trees[spawn_parent] = cls(spawn_parent)

            try:
                child_tree = trees[ob]
            except KeyError:
                trees[ob] = child_tree = cls(ob)
            tree.add_child(child_tree)

        return roots, current_tree

    @classmethod
    def forest(cls):
        """
        forest() -> sequence

        Return a sequence of `GreenletTree`, one for each running
        native thread.
        """

        return list(cls._forest()[0].values())

    @classmethod
    def current_tree(cls):
        """
        current_tree() -> GreenletTree

        Returns the `GreenletTree` for the current thread.
        """
        return cls._forest()[1]
