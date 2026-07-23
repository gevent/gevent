"""
:mod:`concurrent.futures.thread` imported before patching leaves a native lock
registered with :func:`os.register_at_fork`; a greenlet that forks while
another holds it hangs the process. See :issue:`1865`.

The runner catches that hang at its timeout.
"""
import concurrent.futures.thread # MUST come before patch_all(); that's the bug

from gevent import monkey; monkey.patch_all() # pragma: testrunner-no-monkey-combine

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from gevent import testing as greentest


class Test(greentest.TestCase):

    def test_global_shutdown_lock_is_patched(self):
        from gevent.thread import LockType
        self.assertIsInstance(
            concurrent.futures.thread._global_shutdown_lock,
            LockType)

    @greentest.skipOnWindows("Uses fork")
    def test_concurrent_fork_while_lock_held(self):
        # Two workers are needed; a single spawn on the main greenlet never
        # overlaps with ``submit`` holding the lock.
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(self._spawn, range(2)))
        self.assertEqual(statuses, [0, 0])

    @staticmethod
    def _spawn(_i):
        return subprocess.Popen([sys.executable, '-c', 'pass']).wait()


if __name__ == '__main__':
    greentest.main()
