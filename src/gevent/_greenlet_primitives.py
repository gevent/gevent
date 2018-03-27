# -*- coding: utf-8 -*-
# copyright (c) 2018 gevent. See  LICENSE.
# cython: auto_pickle=False,embedsignature=True,always_allow_keywords=False
"""
A collection of primitives used by the hub, and suitable for
compilation with Cython because of their frequency of use.

"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from weakref import ref as wref

from greenlet import greenlet

from gevent.exceptions import BlockingSwitchOutError


# In Cython, we define these as 'cdef inline' functions. The
# compilation unit cannot have a direct assignment to them (import
# is assignment) without generating a 'lvalue is not valid target'
# error.
locals()['getcurrent'] = __import__('greenlet').getcurrent
locals()['greenlet_init'] = lambda: None
locals()['_greenlet_switch'] = greenlet.switch

__all__ = [
    'TrackedRawGreenlet',
    'SwitchOutGreenletWithLoop',
]

class TrackedRawGreenlet(greenlet):

    def __init__(self, function, parent):
        greenlet.__init__(self, function, parent)
        # See greenlet.py's Greenlet class. We capture the cheap
        # parts to maintain the tree structure, but we do not capture
        # the stack because that's too expensive for 'spawn_raw'.

        current = getcurrent() # pylint:disable=undefined-variable
        self.spawning_greenlet = wref(current)
        # See Greenlet for how trees are maintained.
        try:
            self.spawn_tree_locals = current.spawn_tree_locals
        except AttributeError:
            self.spawn_tree_locals = {}
            if current.parent:
                current.spawn_tree_locals = self.spawn_tree_locals


class SwitchOutGreenletWithLoop(TrackedRawGreenlet):
    # Subclasses must define:
    # - self.loop

    # This class defines loop in its .pxd for Cython. This lets us avoid
    # circular dependencies with the hub.

    def switch(self):
        switch_out = getattr(getcurrent(), 'switch_out', None) # pylint:disable=undefined-variable
        if switch_out is not None:
            switch_out()
        return _greenlet_switch(self) # pylint:disable=undefined-variable

    def switch_out(self):
        raise BlockingSwitchOutError('Impossible to call blocking function in the event loop callback')

def _init():
    greenlet_init() # pylint:disable=undefined-variable

_init()

from gevent._util import import_c_accel
import_c_accel(globals(), 'gevent.__greenlet_primitives')
