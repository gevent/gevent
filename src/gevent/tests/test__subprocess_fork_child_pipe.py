"""
A child of :mod:`gevent.subprocess` must not read another subprocess's pipe.

The sibling of :mod:`gevent.tests.test__subprocess_fork_child_hub` with the
theft running the other way: a copy of a parent greenlet resumed in the
pre-exec child *reads*, and those bytes never reach the parent that was
capturing them. On a TLS socket that is loud (``bad_record_mac``); a pipe has
no MAC, so it is silent, and the capture is simply short --- in the worst case
empty, which is how it was first seen in production.

Every line the producers write is numbered and fixed-width, so a short read is
arithmetic rather than judgement.
"""
from gevent import monkey; monkey.patch_all() # pragma: testrunner-no-monkey-combine

import os
import subprocess
import sys

import gevent

from gevent import testing as greentest

if hasattr(os, 'register_at_fork'):
    # The least a handler can do and still yield.
    os.register_at_fork(after_in_child=lambda: gevent.sleep(0))

#: Lines per producer. Each is exactly ``LINE_LEN`` bytes with its newline.
LINES = 1500
LINE_LEN = 64
EXPECTED = LINES * LINE_LEN

#: Concurrent producers. One is enough to see the defect on about half the
#: runs; every extra pipe is another chance for a fork window to land while a
#: reader is parked on it, and at this many it showed up on every attempt.
PRODUCERS = 16
SPAWNS = 120

PRODUCER = (
    'import sys, time\n'
    'for i in range(%d):\n'
    '    sys.stdout.write("%%063d\\n" %% i)\n'
    '    sys.stdout.flush()\n'
    '    time.sleep(0.0005)\n'
) % LINES


class Test(greentest.TestCase):

    # The producers alone take a couple of seconds, well past the default.
    __timeout__ = 120

    @greentest.skipOnWindows("Uses the POSIX fork/exec path")
    def test_spawning_does_not_consume_another_pipe(self):
        # Not `with`: all of them have to stay open together, for the whole
        # length of the spawn storm. They are waited on and closed below.
        victims = [
            subprocess.Popen([sys.executable, '-c', PRODUCER], # pylint:disable=consider-using-with
                             stdout=subprocess.PIPE)
            for _ in range(PRODUCERS)
        ]
        chunks = [[] for _ in victims]

        def consume(n):
            read = victims[n].stdout.read
            while True:
                buf = read(4096)
                if not buf:
                    return
                chunks[n].append(buf)

        def spawn_storm():
            for _ in range(SPAWNS):
                subprocess.run([sys.executable, '-c', 'pass'], check=False)
                gevent.sleep(0.005)

        readers = [gevent.spawn(consume, n) for n in range(PRODUCERS)]
        storm = gevent.spawn(spawn_storm)
        try:
            gevent.joinall([storm], timeout=180)
            gevent.joinall(readers, timeout=180)
        finally:
            for victim in victims:
                victim.wait()
                victim.stdout.close()

        short = [
            (n, victims[n].returncode, EXPECTED - len(b''.join(chunks[n])))
            for n in range(PRODUCERS)
            if len(b''.join(chunks[n])) != EXPECTED or victims[n].returncode != 0
        ]
        self.assertEqual(short, [])


if __name__ == '__main__':
    greentest.main()
