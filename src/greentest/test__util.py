# -*- coding: utf-8 -*-
# Copyright 2018 gevent contributes
# See LICENSE for details.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import greentest

import gevent
from gevent import util
from gevent import local

class MyLocal(local.local):
    def __init__(self, foo):
        self.foo = foo

@greentest.skipOnPyPy("5.10.x is *very* slow formatting stacks")
class TestFormat(greentest.TestCase):

    def test_basic(self):
        lines = util.format_run_info()

        value = '\n'.join(lines)
        self.assertIn('Threads', value)
        self.assertIn('Greenlets', value)

        # because it's a raw greenlet, we have no data for it.
        self.assertNotIn("Spawned at", value)
        self.assertNotIn("Parent greenlet", value)
        self.assertNotIn("Spawn Tree Locals", value)

    def test_with_Greenlet(self):
        rl = local.local()
        rl.foo = 1
        def root():
            l = MyLocal(42)
            gevent.getcurrent().spawn_tree_locals['a value'] = 42
            g = gevent.spawn(util.format_run_info)
            g.join()
            return g.value

        g = gevent.spawn(root)
        g.name = 'Printer'
        g.join()
        value = '\n'.join(g.value)

        self.assertIn("Spawned at", value)
        self.assertIn("Parent greenlet", value)
        self.assertIn("Spawn Tree Locals", value)
        self.assertIn("Greenlet Locals:", value)
        self.assertIn('MyLocal', value)
        self.assertIn("Printer", value) # The name is printed


if __name__ == '__main__':
    greentest.main()
