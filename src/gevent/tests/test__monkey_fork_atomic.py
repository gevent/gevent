"""
Nothing may switch greenlets inside ``os.fork()``: :func:`os.register_at_fork`
handlers assume that window is atomic, and ``filelock`` 3.30 enforces it from
an audit hook. Importing :mod:`concurrent.futures.thread` after patching used
to break that. See :issue:`1865`.
"""
from gevent import monkey; monkey.patch_all() # pragma: testrunner-no-monkey-combine

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from gevent import testing as greentest

# Stands in for filelock. Registered after concurrent.futures, so this runs
# first: ``before`` handlers run in reverse.
_forking = []

if hasattr(os, 'register_at_fork'):
    os.register_at_fork(
        before=lambda: _forking.append(1),
        after_in_parent=_forking.pop,
        after_in_child=_forking.clear)

    def _audit(event, _args):
        if event == 'os.fork' and _forking:
            raise RuntimeError("fork began inside another fork")

    sys.addaudithook(_audit)


class Test(greentest.TestCase):

    @greentest.skipOnWindows("Uses fork")
    def test_forks_do_not_overlap(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(self._spawn, range(4)))
        self.assertEqual(statuses, [[0] * 4] * 4)

    @staticmethod
    def _spawn(_i):
        return [subprocess.Popen([sys.executable, '-c', 'pass']).wait()
                for _ in range(4)]


if __name__ == '__main__':
    greentest.main()
