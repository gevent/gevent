from gevent import monkey; monkey.patch_all()
import gevent.hub

# check that the locks initialized by 'threading' did not init the hub
assert gevent.hub._get_hub() is None, 'monkey.patch_all() should not init hub'

import gevent
import gevent.testing as greentest
import threading


def helper():
    threading.currentThread()
    gevent.sleep(0.2)


class Test(greentest.TestCase):

    def _do_test(self, spawn):
        before = len(threading._active)
        g = spawn(helper)
        gevent.sleep(0.1)
        self.assertEqual(len(threading._active), before + 1)
        try:
            g.join()
        except AttributeError:
            while not g.dead:
                gevent.sleep()
            # Raw greenlet has no join(), uses a weakref to cleanup.
            # so the greenlet has to die. On CPython, it's enough to
            # simply delete our reference.
            del g
            # On PyPy, it might take a GC, but for some reason, even
            # running several GC's doesn't clean it up under 5.6.0.
            # So we skip the test.
            #import gc
            #gc.collect()

        self.assertEqual(len(threading._active), before)


    def test_cleanup_gevent(self):
        self._do_test(gevent.spawn)

    @greentest.skipOnPyPy("weakref is not cleaned up in a timely fashion")
    def test_cleanup_raw(self):
        self._do_test(gevent.spawn_raw)

if __name__ == '__main__':
    greentest.main()
