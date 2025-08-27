import errno
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch as Patch

import gevent.core
import gevent.testing as greentest
from gevent import get_hub
from gevent import os
from gevent import select
from gevent import socket
from gevent.testing import timing


class TestSelect(gevent.testing.timing.AbstractGenericWaitTestCase):

    def wait(self, timeout):
        select.select([], [], [], timeout)



@greentest.skipOnWindows("Cant select on files")
class TestSelectRead(gevent.testing.timing.AbstractGenericWaitTestCase):

    def wait(self, timeout):
        r, w = os.pipe()
        try:
            select.select([r], [], [], timeout)
        finally:
            os.close(r)
            os.close(w)

    # Issue #12367: http://www.freebsd.org/cgi/query-pr.cgi?pr=kern/155606
    @unittest.skipIf(sys.platform.startswith('freebsd'),
                     'skip because of a FreeBSD bug: kern/155606')
    def test_errno(self):
        # Backported from test_select.py in 3.4
        with open(__file__, 'rb') as fp:
            fd = fp.fileno()
            fp.close()
            try:
                select.select([fd], [], [], 0)
            except OSError as err:
                # Python 3
                self.assertEqual(err.errno, errno.EBADF)
            else:
                self.fail("exception not raised")


@unittest.skipUnless(hasattr(select, 'poll'), "Needs poll")
@greentest.skipOnWindows("Cant poll on files")
class TestPollRead(gevent.testing.timing.AbstractGenericWaitTestCase):
    def wait(self, timeout):
        # On darwin, the read pipe is reported as writable
        # immediately, for some reason. So we carefully register
        # it only for read events (the default is read and write)
        r, w = os.pipe()
        try:
            poll = select.poll()
            poll.register(r, select.POLLIN)
            poll.poll(timeout * 1000)
        finally:
            poll.unregister(r)
            os.close(r)
            os.close(w)

    def test_unregister_never_registered(self):
        # "Attempting to remove a file descriptor that was
        # never registered causes a KeyError exception to be
        # raised."
        poll = select.poll()
        self.assertRaises(KeyError, poll.unregister, 5)

    def test_poll_invalid(self):
        self.skipTest(
            "libev >= 4.27 aborts the process if built with EV_VERIFY >= 2. "
            "For libuv, depending on whether the fileno is reused or not "
            "this either crashes or does nothing.")
        with open(__file__, 'rb') as fp:
            fd = fp.fileno()

            poll = select.poll()
            poll.register(fd, select.POLLIN)
            # Close after registering; libuv refuses to even
            # create a watcher if it would get EBADF (so this turns into
            # a test of whether or not we successfully initted the watcher).
            fp.close()
            result = poll.poll(0)
            self.assertEqual(result, [(fd, select.POLLNVAL)]) # pylint:disable=no-member

class TestSelectTypes(greentest.TestCase):

    def test_int(self):
        sock = socket.socket()
        try:
            select.select([int(sock.fileno())], [], [], 0.001)
        finally:
            sock.close()

    def test_iterable(self):
        sock = socket.socket()

        def fileno_iter():
            yield int(sock.fileno())

        try:
            select.select(fileno_iter(), [], [], 0.001)
        finally:
            sock.close()

    def test_string(self):
        self.switch_expected = False
        self.assertRaises(TypeError, select.select, ['hello'], [], [], 0.001)


@greentest.skipOnWindows("Things like os.close don't work on Windows")
class TestPossibleCrashes(greentest.TestCase):
    """
    Tests for the crashes and unexpected exceptions
    that happen when we try to use or create (depending on
    loop implementation) a IO watcher for a closed/invalid file descriptor.

    See https://github.com/gevent/gevent/issues/2100
    See test__selectors.py
    """

    def test_closing_object_while_selecting(self):
        # This one crashed libuv on Linux, at least, with
        #   libuv/src/unix/linux.c:1430: uv__io_poll: Assertion `errno == EEXIST' failed.
        #
        # The expected sequence here is that
        # ``select.select`` creates the watcher objects and starts them.
        # Then, it goes back to the hub, which spawns and runs the greenlet
        # that closes the socket. The hub then goes into the IO waiting loop,
        # at which point libuv calls ``epoll_ctl``, gets EBADF instead of
        # EEXIST, and aborts.
        #
        # Why did this happen? We weren't actually *in* libuv yet when
        # the call to ``socket.close`` happened.
        # I think we deferred the callbacks that *actually* close the socket
        # because a watcher was active. Those run first, then the IO polling
        # begins.
        # Unlike libev, which calls ``epoll_ctl`` at watcher init time,
        # libuv defers this part.
        #
        # We were trying to defer the close of the socket to the next iteration fo
        # the event loop, but:
        # (1) we were using run_callback(), and because we are in a greenlet spawn,
        #     we were already running callbacks; in that situation, a new callback
        #     can run immediately. Which it did, and closed the FD, breaking the loops.
        #     The fix is to use a check watcher instead.
        # (2) libuv doesn't implement the function that lets us determine that we
        #     need to defer the check. (fixing this involved rolling our own.)
        sock = socket.socket()
        self.addCleanup(sock.close)
        gevent.spawn(sock.close)


        # This call needs to be blocking so we get all the way
        # to having an open, started IO watcher when the
        # socket gets closed.
        with Patch.object(select, '_original_select', return_value=((), (), ())):
            select.select([sock], (), (), timing.SMALLEST_RELIABLE_DELAY)

    def _close_invalid_sock(self, sock):
        # Because we closed the FD already (which raises EBADF when done again), but we
        # still need to take care of the gevent-resources
        try:
            sock.close()
        except OSError:
            pass

    def _close_invalid_fd(self, fd):
        try:
            os.close(fd)
        except OSError:
            pass

    def test_closing_fd_while_selecting(self):
        # As above, this causes libuv to crash for the same reasons.
        # On linux/libev with -UNDEBUG to enable assertions, this
        # crashes with:
        #   ev_epoll.c:134: epoll_modify: Assertion
        #   `("libev: I/O watcher with invalid fd found in epoll_ctl",
        #    errno != EBADF && errno != ELOOP && errno != EINVAL)
        #
        # called from ev_run:ev.c:4075 via ev.c:4021
        sock = socket.socket()
        self.addCleanup(self._close_invalid_sock, sock)
        gevent.spawn(self._close_invalid_fd, sock.fileno())
        with Patch.object(select, '_original_select', return_value=((), (), ())):
            select.select([sock], (), (), timing.SMALLEST_RELIABLE_DELAY)

    def test_closing_fd_before_selecting(self):
        # As above, this crashes libuv/linux at:
        #     libuv/src/unix/linux.c:1434
        #
        # if (!epoll_ctl(epollfd, op, fd, &e))
        #   continue;
        #
        # assert(op == EPOLL_CTL_ADD);
        # assert(errno == EEXIST);
        #
        # /* File descriptor that's been watched before, update event mask. */
        # if (epoll_ctl(epollfd, EPOLL_CTL_MOD, fd, &e))
        #   abort(); // <--- 1434
        #
        # Which is UV calling epoll_ctl because it thinks
        # Fatal Python error: Aborted
        # Current thread 0x00007ffffe8450c0 (most recent call first):
        #   File "/project/src/gevent/libuv/loop.py", line 557 in run
        #   File "/project/src/gevent/hub.py", line 647 in run

        sock = socket.socket()
        self.addCleanup(self._close_invalid_sock, sock)
        os.close(sock.fileno())
        with Patch.object(select, '_original_select', return_value=((), (), ())):
            with self._check_os_error_on_libuv():
                select.select([sock], (), (), timing.SMALLEST_RELIABLE_DELAY)


    @contextmanager
    def _check_os_error_on_libuv(self):
        try:
            yield
        except OSError:
            self.assertIn('gevent.libuv', type(get_hub().loop).__module__ )


    def test_closing_object_while_polling(self):
        # Polling is different because registering is when we
        # create the IO watcher; we just don't start it until
        # we poll.
        sock = socket.socket()
        self.addCleanup(sock.close)
        orig_fileno = sock.fileno()
        gevent.spawn(sock.close)
        # This call needs to be blocking so we get all the way
        # to having an open, started IO watcher when the
        # socket gets closed.
        poller = select.poll()
        poller.register(sock, select.POLLIN)

        with Patch.object(select, '_original_select', return_value=((), (), ())):
            fds_and_events = None
            # pylint:disable=unbalanced-tuple-unpacking
            with self._check_os_error_on_libuv():
                # libuv gives us POLLIN and POLLNVAL
                fds_and_events = poller.poll(timing.SMALLEST_RELIABLE_DELAY)
            if fds_and_events is not None:
                self.assertTrue(len(fds_and_events) >= 1)
                [(fd, event)] = [x for x in fds_and_events if x[1] == select.POLLIN]
                self.assertEqual(fd, orig_fileno)
                self.assertEqual(event, select.POLLIN)

            fds_and_events = None
            with self._check_os_error_on_libuv():
                fds_and_events = poller.poll(timing.SMALLEST_RELIABLE_DELAY) # this one
                # crashes # the process
            if fds_and_events is not None:
                [(fd, event)] = fds_and_events
                self.assertEqual(fd, orig_fileno)
                self.assertEqual(event, select.POLLNVAL)

if __name__ == '__main__':
    greentest.main()
