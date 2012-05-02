import gevent.core
import unittest

class Test(unittest.TestCase):

    if hasattr(gevent.core, 'child'):

        def test(self):
            loop = gevent.core.loop('nochild', default=True)
            self.assertRaises(TypeError, loop.child, 1)

            loop = gevent.core.loop(default=False)
            self.assertRaises(TypeError, loop.child, 1)


if __name__ == '__main__':
    unittest.main()
