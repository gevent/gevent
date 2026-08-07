import _thread
import time


# This module monkey-patches at import time and depends on a fresh native-thread
# state. It must run in its own subprocess.
# pragma: testrunner-no-combine


# Capture the native APIs before monkey-patching. The producer must not be a
# gevent-managed thread and must never create a hub of its own.
native_start_new_thread = _thread.start_new_thread
native_get_ident = _thread.get_ident
native_sleep = time.sleep

from gevent import monkey
monkey.patch_all()

import gevent
from gevent._hub_local import get_hub_if_exists
from gevent.lock import BoundedSemaphore
import gevent.testing as greentest


class TestHublessThreadSemaphore(greentest.TestCase):

    __timeout__ = 10

    def _wait_for(self, condition):
        with gevent.Timeout(2):
            while not condition():
                gevent.sleep(0.001)

    def _run_waiters(self, semaphore, count, release):
        owner_ident = native_get_ident()
        notified_on = []
        resumed_on = []

        semaphore.rawlink(
            lambda _: notified_on.append(native_get_ident())
        )

        def waiter():
            semaphore.acquire()
            resumed_on.append(native_get_ident())
            semaphore.release()

        waiters = [gevent.spawn(waiter) for _ in range(count)]
        self._wait_for(lambda: semaphore.linkcount() == count + 1)
        release()
        gevent.joinall(waiters, timeout=2)

        self.assertTrue(all(waiter.successful() for waiter in waiters))
        self.assertEqual(notified_on, [owner_ident])
        self.assertEqual(resumed_on, [owner_ident] * count)

    def _run_native_round(self, owner_ident):
        semaphore = BoundedSemaphore(1)
        acquired = []
        release_requested = []
        released = []
        producer_ident = []
        producer_hub = []

        def producer():
            producer_ident.append(native_get_ident())
            producer_hub.append(get_hub_if_exists())
            semaphore.acquire()
            acquired.append(True)
            while not release_requested:
                native_sleep(0.001)
            semaphore.release()
            released.append(True)

        native_start_new_thread(producer, ())
        self._wait_for(lambda: acquired)
        self._run_waiters(
            semaphore,
            4,
            lambda: release_requested.append(True),
        )
        self._wait_for(lambda: released)

        self.assertNotEqual(producer_ident, [owner_ident])
        self.assertEqual(producer_hub, [None])

    def test_hubless_native_thread_release_wakes_waiters(self):
        owner_ident = native_get_ident()
        for _ in range(20):
            self._run_native_round(owner_ident)

    def test_owner_thread_release_wakes_waiters(self):
        semaphore = BoundedSemaphore(1)
        semaphore.acquire()
        self._run_waiters(semaphore, 2, semaphore.release)

    def test_gevent_producer_release_wakes_waiters(self):
        semaphore = BoundedSemaphore(1)
        semaphore.acquire()
        producer = gevent.Greenlet(semaphore.release)
        self._run_waiters(semaphore, 2, producer.start)
        producer.get(timeout=2)


if __name__ == '__main__':
    greentest.main()
