"""
A forked child must keep serving on a listener it inherited.

The other side of :mod:`gevent.tests.test__fork_child_waits`: that one requires
the child to resume none of the parent's blocked greenlets, this one requires it
to keep using the objects those greenlets were blocked on, which is what
gevent's bind/fork/accept server pattern does.

Cancelling a wait must therefore leave the object fit to use. The second case
pins that down: there the listener's io watcher is live at the fork, and a child
that inherits it still holding the parent's accept raises
``ConcurrentObjectUseError`` instead of serving.

See :issue:`2204`.
"""
from gevent import monkey; monkey.patch_all() # pragma: testrunner-no-monkey-combine

import os
import socket
import time

import gevent

from gevent import testing as greentest

if hasattr(os, 'register_at_fork'):
    # Without a handler that yields, the child runs none of the parent's
    # greenlets anyway and the test cannot tell the two behaviours apart.
    os.register_at_fork(after_in_child=lambda: gevent.sleep(0))


def _serve_until(listener, deadline): # pragma: no cover
    # Runs in the forked child and never returns. Exit 3 means it accepted
    # nothing, 2 means it raised, which is what a listener still holding the
    # parent's accept produces.
    served = 0
    listener.settimeout(0.2)
    try:
        while time.monotonic() < deadline:
            try:
                conn, _ = listener.accept()
            except OSError:
                continue
            try:
                data = conn.recv(64)
                if data:
                    conn.sendall(data)
                    served += 1
            finally:
                conn.close()
    except BaseException: # pylint:disable=broad-except
        os._exit(2)
    os._exit(0 if served else 3)


def _hammer(port, deadline, start, step, ok, bad):
    i = start
    while time.monotonic() < deadline - 0.3:
        payload = b'%08d' % (i % 100000000)
        try:
            sock = socket.create_connection(('127.0.0.1', port), timeout=5)
            sock.sendall(payload)
            got = sock.recv(8)
            sock.close()
        except OSError:
            bad.append(1)
            gevent.sleep(0.01)
            continue
        if got == payload:
            ok.append(1)
        else:
            bad.append(1)
        i += step


@greentest.skipIf(
    greentest.LIBUV and greentest.OSX,
    "libuv cannot fork and continue on macOS: its backend there is kqueue, whose "
    "descriptors are not inherited, so the child aborts inside uv_async_send. "
    "gevent's own libuv loop.reinit says as much."
)
class Test(greentest.TestCase):

    __timeout__ = 60

    WORKERS = 2
    CLIENTS = 4
    BUSY = 4
    DURATION = 1.5

    def _run(self, park_an_acceptor):
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        port = listener.getsockname()[1]

        stop = []

        def busy():
            # Parked on a timer across the fork, so the child has copies worth
            # cancelling.
            while not stop:
                gevent.sleep(0.002)

        busies = [gevent.spawn(busy) for _ in range(self.BUSY)]
        acceptor = gevent.spawn(listener.accept) if park_an_acceptor else None
        gevent.sleep(0.1)

        deadline = time.monotonic() + self.DURATION
        children = []
        for _ in range(self.WORKERS):
            pid = os.fork()
            if pid == 0:
                _serve_until(listener, deadline)
            children.append(pid)

        if acceptor is not None:
            acceptor.kill(block=False)

        ok = []
        bad = []
        clients = [
            gevent.spawn(_hammer, port, deadline, n, self.CLIENTS, ok, bad)
            for n in range(self.CLIENTS)
        ]
        gevent.joinall(clients, timeout=self.DURATION + 20)
        stop.append(1)
        gevent.joinall(busies, timeout=10)

        # Not os.waitpid(pid, 0): see greentest.wait_for_child. Both children
        # exit at once here, which loses that race most often.
        statuses = [greentest.wait_for_child(pid, timeout=20) for pid in children]
        listener.close()

        self.assertEqual(statuses, [0] * self.WORKERS)
        self.assertEqual(bad, [])
        self.assertNotEqual(ok, [])

    @greentest.skipOnWindows("Uses fork")
    def test_child_serves_on_inherited_listener(self):
        self._run(park_an_acceptor=False)

    @greentest.skipOnWindows("Uses fork")
    def test_child_serves_when_parent_was_accepting(self):
        self._run(park_an_acceptor=True)


if __name__ == '__main__':
    greentest.main()
