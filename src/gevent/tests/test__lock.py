from gevent import lock


import gevent.testing as greentest
from gevent.tests import test__semaphore


class TestRLockMultiThread(test__semaphore.TestSemaphoreMultiThread):

    def _makeOne(self):
        # If we don't set the hub before returning,
        # there's a potential race condition, if the implementation
        # isn't careful. If it's the background hub that winds up capturing
        # the hub, it will ask the hub to switch back to itself and
        # then switch to the hub, which will raise LoopExit (nothing
        # for the background thread to do). What is supposed to happen
        # is that the background thread realizes it's the background thread,
        # starts an async watcher and then switches to the hub.
        #
        # So we deliberately don't set the hub to help test that condition.
        return lock.RLock()

    def assertOneHasNoHub(self, sem):
        self.assertIsNone(sem._block.hub)


class TestLockReinitAfterFork(greentest.TestCase):

    def test_it(self):
        # See https://github.com/gevent/gevent/issues/1895

        # Make sure we carefully handle forking while running callbacks
        # of a lock/_AbstractLinkable object.
        import sys
        import subprocess
        import textwrap
        import os

        if not hasattr(os, 'fork'):
            self.skipTest('Requires os.fork')

        script =textwrap.dedent("""\
        from gevent import monkey
        monkey.patch_all()

        from gevent import spawn

        import os
        from logging import Handler
        from threading import Event
        handler = Handler()
        handler.acquire()

        event = Event()

        def forker():
            event.set()
            handler.acquire()
            handler.release()
            os.fork()

        g = spawn(forker)
        event.wait()
        handler.release()
        g.join()
        """)

        output = subprocess.check_output(
            [sys.executable, '-c', script],
            stderr=subprocess.STDOUT,
        ).decode('utf-8')

        # We used to print a failing AssertionError to stdout,
        # that should no longer be the case.
        self.assertFalse(output)

if __name__ == '__main__':
    greentest.main()
