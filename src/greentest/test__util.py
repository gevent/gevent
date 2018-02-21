# -*- coding: utf-8 -*-
# Copyright 2018 gevent contributes
# See LICENSE for details.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import greentest

import gevent
from gevent import util


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
        def root():
            gevent.getcurrent().spawn_tree_locals['a value'] = 42
            g = gevent.spawn(util.format_run_info)
            g.join()
            return g.value

        g = gevent.spawn(root)
        g.join()
        value = '\n'.join(g.value)

        self.assertIn("Spawned at", value)
        self.assertIn("Parent greenlet", value)
        self.assertIn("Spawn Tree Locals", value)


if __name__ == '__main__':
    greentest.main()
