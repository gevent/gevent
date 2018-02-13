from __future__ import print_function
from gevent import config

from greentest import TestCase
from greentest import main
from greentest import LARGE_TIMEOUT
from greentest.sysinfo import CFFI_BACKEND


class Test(TestCase):
    __timeout__ = LARGE_TIMEOUT

    repeat = 0

    def setUp(self):
        self.called = []
        self.loop = config.loop(default=False)
        self.timer = self.loop.timer(0.001, repeat=self.repeat)

    def cleanup(self):
        # cleanup instead of tearDown to cooperate well with
        # leakcheck.py
        self.timer.close()
        # cycle the loop so libuv close callbacks fire
        self.loop.run()
        self.loop.destroy()
        self.loop = None
        self.timer = None

    def f(self, x=None):
        self.called.append(1)
        if x is not None:
            x.stop()

    def assertTimerInKeepalive(self):
        if CFFI_BACKEND:
            self.assertIn(self.timer, self.loop._keepaliveset)

    def assertTimerNotInKeepalive(self):
        if CFFI_BACKEND:
            self.assertNotIn(self.timer, self.loop._keepaliveset)

    def test_main(self):
        loop = self.loop
        x = self.timer
        x.start(self.f)
        self.assertTimerInKeepalive()
        self.assertTrue(x.active, x)

        with self.assertRaises((AttributeError, ValueError)):
            x.priority = 1

        loop.run()
        self.assertEqual(x.pending, 0)
        self.assertEqual(self.called, [1])
        self.assertIsNone(x.callback)
        self.assertIsNone(x.args)

        if x.priority is not None:
            self.assertEqual(x.priority, 0)
            x.priority = 1
            self.assertEqual(x.priority, 1)

        x.stop()
        self.assertTimerNotInKeepalive()

class TestAgain(Test):
    repeat = 1

    def test_main(self):
        # Again works for a new timer
        x = self.timer
        x.again(self.f, x)
        self.assertTimerInKeepalive()

        self.assertEqual(x.args, (x,))

        # XXX: On libev, this takes 1 second. On libuv,
        # it takes the expected time.
        self.loop.run()

        self.assertEqual(self.called, [1])

        x.stop()
        self.assertTimerNotInKeepalive()


if __name__ == '__main__':
    main()
