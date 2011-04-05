import gevent
import unittest


class Test(unittest.TestCase):

    def test_types(self):
        loop = gevent.core.loop()
        lst = []

        io = loop.timer(0.01)

        # test that cannot pass non-callable thing to start()
        self.assertRaises(TypeError, io.start, None)
        self.assertRaises(TypeError, io.start, 5)
        # test that cannot set 'callback' to non-callable thing later either
        io.start(lambda *args: lst.append(args))
        self.assertEqual(io.args, ())
        try:
            io.callback = None
            raise AssertionError('"io.callback = None" must raise TypeError')
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
        try:
            io.args = 5
            raise AssertionError('"io.args = 5" must raise TypeError')
        except TypeError:
            pass
        self.assertEqual(io.args, (1, 2, 3))
        try:
            io.args = [4, 5]
            raise AssertionError('"io.args = [4, 5]" must raise TypeError')
        except TypeError:
            pass
        self.assertEqual(io.args, (1, 2, 3))
        # None also works, means empty tuple
        io.args = None
        loop.run()
        self.assertEqual(lst, [()])

        io.start(reset, io, lst)
        del io
        loop.run()
        self.assertEqual(lst, [(), 25])


def reset(watcher, lst):
    watcher.args = None
    watcher.callback = lambda: None
    lst.append(25)


if __name__ == '__main__':
    unittest.main()
