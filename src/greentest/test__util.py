# -*- coding: utf-8 -*-
# Copyright 2018 gevent contributes
# See LICENSE for details.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import gc

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
            assert l
            gevent.getcurrent().spawn_tree_locals['a value'] = 42
            g = gevent.spawn(util.format_run_info)
            g.join()
            return g.value

        g = gevent.spawn(root)
        g.name = 'Printer'
        g.join()
        value = '\n'.join(g.value)

        self.assertIn("Spawned at", value)
        self.assertIn("Parent:", value)
        self.assertIn("Spawn Tree Locals", value)
        self.assertIn("Greenlet Locals:", value)
        self.assertIn('MyLocal', value)
        self.assertIn("Printer", value) # The name is printed

@greentest.skipOnPyPy("See TestFormat")
class TestTree(greentest.TestCase):

    @greentest.ignores_leakcheck
    def test_tree(self):
        # pylint:disable=too-many-locals
        # Python 2.7 on Travis seems to show unexpected greenlet objects
        # so perhaps we need a GC?
        gc.collect()
        gc.collect()

        import re
        glets = []
        l = MyLocal(42)
        assert l

        def s(f):
            g = gevent.spawn(f)
            # Access this in spawning order for consistent sorting
            # at print time in the test case.
            getattr(g, 'minimal_ident')
            return g

        def t1():
            raise greentest.ExpectedException()

        def t2():
            l = MyLocal(16)
            assert l
            return s(t1)

        s1 = s(t2)
        s1.join()

        glets.append(s(t2))

        def t3():
            return s(t2)

        s3 = s(t3)
        s3.spawn_tree_locals['stl'] = 'STL'
        s3.join()


        s4 = s(util.GreenletTree.current_tree)
        s4.join()

        tree = s4.value
        self.assertTrue(tree.root)

        self.assertNotIn('Parent', str(tree)) # Simple output
        value = tree.format(details={'stacks': False})
        hexobj = re.compile('0x[0123456789abcdef]+L?', re.I)
        value = hexobj.sub('X', value)
        value = value.replace('epoll', 'select')
        value = value.replace('select', 'default')
        value = value.replace('test__util', '__main__')
        value = re.compile(' fileno=.').sub('', value)
        value = value.replace('ref=-1', 'ref=0')

        self.maxDiff = None
        expected = """\
<greenlet.greenlet object at X>
 :    Greenlet Locals:
 :      Local <class '__main__.MyLocal'> at X
 :        {'foo': 42}
 +--- <QuietHub at X default default pending=0 ref=0>
 :          Parent: <greenlet.greenlet object at X>
 +--- <Greenlet "Greenlet-1" at X: _run>; finished with value <Greenlet "Greenlet-0" at X
 :          Parent: <QuietHub at X default default pending=0 ref=0>
 |    +--- <Greenlet "Greenlet-0" at X: _run>; finished with exception ExpectedException()
 :                Parent: <QuietHub at X default default pending=0 ref=0>
 +--- <Greenlet "Greenlet-2" at X: _run>; finished with value <Greenlet "Greenlet-4" at X
 :          Parent: <QuietHub at X default default pending=0 ref=0>
 |    +--- <Greenlet "Greenlet-4" at X: _run>; finished with exception ExpectedException()
 :                Parent: <QuietHub at X default default pending=0 ref=0>
 +--- <Greenlet "Greenlet-3" at X: _run>; finished with value <Greenlet "Greenlet-5" at X
 :          Parent: <QuietHub at X default default pending=0 ref=0>
 :          Spawn Tree Locals
 :          {'stl': 'STL'}
 |    +--- <Greenlet "Greenlet-5" at X: _run>; finished with value <Greenlet "Greenlet-6" at X
 :                Parent: <QuietHub at X default default pending=0 ref=0>
 |         +--- <Greenlet "Greenlet-6" at X: _run>; finished with exception ExpectedException()
 :                      Parent: <QuietHub at X default default pending=0 ref=0>
 +--- <Greenlet "Greenlet-7" at X: _run>; finished with value <gevent.util.GreenletTree obje
            Parent: <QuietHub at X default default pending=0 ref=0>
        """.strip()
        self.assertEqual(value, expected)

if __name__ == '__main__':
    greentest.main()
