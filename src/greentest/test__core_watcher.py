from __future__ import absolute_import, print_function
import unittest
import greentest
from gevent import core

IS_CFFI = hasattr(core, 'libuv') or hasattr(core, 'libev')

class Test(greentest.TestCase):

    __timeout__ = None

    def test_types(self):
        loop = core.loop(default=False)
        lst = []

        io = loop.timer(0.01)

        # test that cannot pass non-callable thing to start()
        self.assertRaises(TypeError, io.start, None)
        self.assertRaises(TypeError, io.start, 5)
        # test that cannot set 'callback' to non-callable thing later either
        io.start(lambda *args: lst.append(args))
        self.assertEqual(io.args, ())
        try:
            io.callback = False
            raise AssertionError('"io.callback = False" must raise TypeError')
        except TypeError:
            pass
        try:
            io.callback = 5
            raise AssertionError('"io.callback = 5" must raise TypeError')
        except TypeError:
            pass
        # test that args can be changed later
        io.args = (1, 2, 3)
        # test that only tuple and None are accepted by 'args' attribute
        self.assertRaises(TypeError, setattr, io, 'args', 5)
        self.assertEqual(io.args, (1, 2, 3))

        self.assertRaises(TypeError, setattr, io, 'args', [4, 5])
        self.assertEqual(io.args, (1, 2, 3))
        # None also works, means empty tuple
        # XXX why?
        io.args = None
        self.assertEqual(io.args, None)
        time_f = getattr(core, 'time', loop.now)
        start = time_f()
        loop.run()
        took = time_f() - start
        self.assertEqual(lst, [()])
        if hasattr(core, 'time'):
            # only useful on libev
            assert took < 1, took

        io.start(reset, io, lst)
        del io
        loop.run()
        self.assertEqual(lst, [(), 25])
        loop.destroy()

    def test_invalid_fd(self):
        # XXX: windows?
        loop = core.loop(default=False)

        # Negative case caught everywhere
        self.assertRaises(ValueError, loop.io, -1, core.READ)

        loop.destroy()


    def test_reuse_io(self):
        loop = core.loop(default=False)

        # Watchers aren't reused once all outstanding
        # refs go away
        tty_watcher = loop.io(1, core.WRITE)
        watcher_handle = tty_watcher._watcher if IS_CFFI else tty_watcher

        del tty_watcher
        # XXX: Note there is a cycle in the CFFI code
        # from watcher_handle._handle -> watcher_handle.
        # So it doesn't go away until a GC runs. However, for libuv
        # it only goes away on PyPy or CPython >= 3.4; prior to that the libuv
        # __del__ method makes the cycle immortal!
        import gc
        gc.collect()

        tty_watcher = loop.io(1, core.WRITE)
        self.assertIsNot(tty_watcher._watcher if IS_CFFI else tty_watcher, watcher_handle)

        loop.destroy()

def reset(watcher, lst):
    watcher.args = None
    watcher.callback = lambda: None
    lst.append(25)


if __name__ == '__main__':
    greentest.main()
