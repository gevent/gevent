"""
A forked child must not resume greenlets that were blocked at the fork.

A runnable greenlet sits on the loop's callback queue; a blocked one is parked
on a watcher, and the loop resumes it from there without consulting that queue.
The workers here sleep between writes, so at any fork most are parked rather
than queued, and the child does nothing but ``os._exit(0)``: every line bearing
a child's pid was written by a copy of somebody else's greenlet.

See :issue:`2204`.
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

    __timeout__ = 60

    WORKERS = 4
    FORKS = 20

    @greentest.skipOnWindows("Uses fork")
    def test_child_resumes_none_of_the_parents_blocked_greenlets(self):
        fileno, path = tempfile.mkstemp(prefix='gevent-fork-child-waits-')
        os.close(fileno)
        fileno = os.open(path, os.O_WRONLY | os.O_APPEND)
        parent = os.getpid()
        stop = []

        def worker(n):
            while not stop:
                # Parked on a timer, not sitting in the callback queue.
                gevent.sleep(0.002)
                # Stands in for the application's side effect.
                os.write(fileno, b'worker=%d pid=%d\n' % (n, os.getpid()))

        workers = [gevent.spawn(worker, n) for n in range(self.WORKERS)]
        try:
            gevent.sleep(0.05)
            for _ in range(self.FORKS):
                pid = os.fork()
                if pid == 0:
                    os._exit(0)
                # Not os.waitpid(pid, 0): see greentest.wait_for_child.
                greentest.wait_for_child(pid, timeout=20)
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
