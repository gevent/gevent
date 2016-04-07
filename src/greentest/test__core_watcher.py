import greentest
from gevent import core


class Test(greentest.TestCase):

    __timeout__ = None

    def test_types(self):
        loop = core.loop()
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
        start = core.time()
        loop.run()
        took = core.time() - start
        self.assertEqual(lst, [()])
        assert took < 1, took

        io.start(reset, io, lst)
        del io
        loop.run()
        self.assertEqual(lst, [(), 25])


def reset(watcher, lst):
    watcher.args = None
    watcher.callback = lambda: None
    lst.append(25)


if __name__ == '__main__':
    greentest.main()
