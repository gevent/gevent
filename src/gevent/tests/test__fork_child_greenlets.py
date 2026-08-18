"""
A forked child must not run copies of the parent's greenlets.

Only the greenlet that forked survives a fork; everything else in the child's
hub is a copy. ``os.register_at_fork(after_in_child=)`` handlers run inside
``fork()`` before it returns, and under monkey-patching they yield, which hands
the child's hub whatever the parent had queued.

See :issue:`2202`.
"""
from gevent import monkey; monkey.patch_all() # pragma: testrunner-no-monkey-combine

import os
import tempfile

import gevent

from gevent import testing as greentest

if hasattr(os, 'register_at_fork'):
    # The least a handler can do and still yield.
    os.register_at_fork(after_in_child=lambda: gevent.sleep(0))


class Test(greentest.TestCase):

    WORKERS = 4
    FORKS = 10

    @greentest.skipOnWindows("Uses fork")
    def test_child_runs_none_of_the_parents_greenlets(self):
        # A file with O_APPEND, not a list: the writer we are trying to catch
        # is a different process, so its testimony cannot come back in the
        # heap, and it would not survive an exec if it did.
        fileno, path = tempfile.mkstemp(prefix='gevent-fork-child-greenlets-')
        os.close(fileno)
        fileno = os.open(path, os.O_WRONLY | os.O_APPEND)
        parent = os.getpid()
        stop = []

        def worker(n):
            while not stop:
                # Stands in for the application's side effect.
                os.write(fileno, b'worker=%d pid=%d\n' % (n, os.getpid()))
                gevent.sleep(0)

        workers = [gevent.spawn(worker, n) for n in range(self.WORKERS)]
        try:
            gevent.sleep(0.05)
            for _ in range(self.FORKS):
                pid = os.fork()
                if pid == 0:
                    # Do nothing whatsoever, and leave. Anything written by
                    # this pid was written by a copy of somebody else's
                    # greenlet, inside os.fork(), before it returned.
                    os._exit(0)
                os.waitpid(pid, 0)
                gevent.sleep(0.01)
        finally:
            stop.append(1)
            gevent.joinall(workers, timeout=10)
            os.close(fileno)

        try:
            with open(path, encoding='ascii') as f:
                strangers = sorted({
                    int(line.rsplit('pid=', 1)[1])
                    for line in f
                } - {parent})
        finally:
            os.unlink(path)

        self.assertEqual(strangers, [])


if __name__ == '__main__':
    greentest.main()
