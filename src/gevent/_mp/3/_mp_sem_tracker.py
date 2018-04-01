from multiprocessing.semaphore_tracker import SemaphoreTracker as _SemaphoreTracker

from gevent.os import make_nonblocking, nb_write

__implements__ = ["SemaphoreTracker", "_semaphore_tracker", "ensure_running",
                  "register", "unregister", "getfd"]
__target__ = "multiprocessing.semaphore_tracker"


class SemaphoreTracker(_SemaphoreTracker):
    def ensure_running(self):
        super().ensure_running()
        make_nonblocking(self._fd)

    def _send(self, cmd, name):
        self.ensure_running()
        msg = '{0}:{1}\n'.format(cmd, name).encode('ascii')
        if len(name) > 512:
            # posix guarantees that writes to a pipe of less than PIPE_BUF
            # bytes are atomic, and that PIPE_BUF >= 512
            raise ValueError('name too long')
        nbytes = nb_write(self._fd, msg)
        assert nbytes == len(msg)


_semaphore_tracker = SemaphoreTracker()
ensure_running = _semaphore_tracker.ensure_running
register = _semaphore_tracker.register
unregister = _semaphore_tracker.unregister
getfd = _semaphore_tracker.getfd
