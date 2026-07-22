"""
Tests specifically for the monkey-patched threading module.
"""
from gevent import monkey; monkey.patch_all() # pragma: testrunner-no-monkey-combine
import gevent.hub

# check that the locks initialized by 'threading' did not init the hub.

# Beginning in Python 3.15, on Linux kernels new enough, importing
# ``subprocess`` attempts to check whether pidfd is available. This leads
# it to call ``os.close(pidfd)``. If we've already monkey-patched ``os``
# at that point, the hub gets created. The order of module patching
# is somewhat undefined: it relies on ``locals()`` and dictionary iteration
# order, so effectively it's the order of arguments to ``patch_all``, which
# we cannot currently change. A release early 2027 can do that, so
# we might be able to fix this problem then by moving os after subprocess,
# though I'm hesitant to change patch order because we know it works, even if
# accidentally. In the meantime, we changed ``gevent.os.close`` to not init
# the hub.
assert (gevent.hub._get_hub() is None
), 'monkey.patch_all() should not init hub'

import gevent
import gevent.testing as greentest
import threading


def helper():
    threading.current_thread()
    gevent.sleep(0.2)

class TestCleanup(greentest.TestCase):

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


class TestLockThread(greentest.TestCase):

    def _spawn(self, func):
        t = threading.Thread(target=func)
        t.start()
        return t

    def test_spin_lock_switches(self):
        # https://github.com/gevent/gevent/issues/1464
        # pylint:disable=consider-using-with
        lock = threading.Lock()
        lock.acquire()
        spawned = []

        def background():
            spawned.append(True)
            while not lock.acquire(False):
                pass

        thread = threading.Thread(target=background)
        # If lock.acquire(False) doesn't yield when it fails,
        # then this never returns.
        thread.start()
        # Verify it tried to run
        self.assertEqual(spawned, [True])
        # We can attempt to join it, which won't work.
        thread.join(0)
        # We can release the lock and then it will acquire.
        lock.release()
        thread.join()


class TestLockGreenlet(TestLockThread):

    def _spawn(self, func):
        return gevent.spawn(func)

if __name__ == '__main__':
    greentest.main()
