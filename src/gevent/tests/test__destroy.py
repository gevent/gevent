from __future__ import absolute_import, print_function

import gevent
import unittest

from gevent.hub import Hub

class TestDestroyHub(unittest.TestCase):

    def test_destroy_hub(self):
        # Loop of initial Hub is default loop.
        hub = gevent.get_hub()
        self.assertTrue(hub.loop.default)

        # Save `gevent.core.loop` object for later comparison.
        initloop = hub.loop

        # Increase test complexity via threadpool creation.
        # Implicitly creates fork watcher connected to the current event loop.
        tp = hub.threadpool
        self.assertIsNotNone(tp)

        # Destroy hub. Does not destroy libev default loop if not explicitly told to.
        hub.destroy()

        # Create new hub. Must re-use existing libev default loop.
        hub = gevent.get_hub()
        self.assertTrue(hub.loop.default)

        # Ensure that loop object is identical to the initial one.
        self.assertIs(hub.loop, initloop)

        # Destroy hub including default loop.
        hub.destroy(destroy_loop=True)

        # Create new hub and explicitly request creation of a new default loop.
        # (using default=True, but that's no longer possible.)
        hub = gevent.get_hub()
        self.assertTrue(hub.loop.default)

        # `gevent.core.loop` objects as well as libev loop pointers must differ.
        self.assertIsNot(hub.loop, initloop)
        self.assertIsNot(hub.loop.ptr, initloop.ptr)
        self.assertNotEqual(hub.loop.ptr, initloop.ptr)

        # Destroy hub including default loop. The default loop regenerates.
        hub.destroy(destroy_loop=True)
        hub = gevent.get_hub()
        self.assertTrue(hub.loop.default)

        hub.destroy()


class TestDestroyedHubRepr(unittest.TestCase):

    def test_repr_after_destroy(self):
        # Uses Hub directly: the test suite installs QuietHub, whose
        # class-level _resolver/_threadpool defaults hide this bug.
        hub = Hub(default=False)
        # destroy() only clears the attributes that were created.
        self.assertIsNotNone(hub.threadpool)
        self.assertIsNotNone(hub.resolver)

        hub.destroy(destroy_loop=True)

        # destroy() sets these to None instead of deleting them, so
        # __repr__, which reads both, still works.
        self.assertIsNone(hub._threadpool)
        self.assertIsNone(hub._resolver)
        self.assertIn('destroyed', repr(hub))


if __name__ == '__main__':
    unittest.main() # pragma: testrunner-no-combine
