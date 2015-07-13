"""
This module provides cooperative versions of os.read() and os.write().
On Posix platforms this uses non-blocking IO, on Windows a threadpool
is used.
"""

from __future__ import absolute_import

import os
import sys
from gevent.hub import get_hub, reinit, PY3
import errno

EAGAIN = getattr(errno, 'EAGAIN', 11)

try:
    import fcntl
except ImportError:
    fcntl = None

__implements__ = ['fork']
__extensions__ = ['tp_read', 'tp_write']

_read = os.read
_write = os.write


ignored_errors = [EAGAIN, errno.EINTR]


if fcntl:

    __extensions__ += ['make_nonblocking', 'nb_read', 'nb_write']

    def make_nonblocking(fd):
        flags = fcntl.fcntl(fd, fcntl.F_GETFL, 0)
        if not bool(flags & os.O_NONBLOCK):
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            return True

    def nb_read(fd, n):
        """Read up to `n` bytes from file descriptor `fd`. Return a string
        containing the bytes read. If end-of-file is reached, an empty string
        is returned.

        The descriptor must be in non-blocking mode.
        """
        hub, event = None, None
        while True:
            try:
                return _read(fd, n)
            except OSError as e:
                if e.errno not in ignored_errors:
                    raise
                if not PY3:
                    sys.exc_clear()
            if hub is None:
                hub = get_hub()
                event = hub.loop.io(fd, 1)
            hub.wait(event)

    def nb_write(fd, buf):
        """Write bytes from buffer `buf` to file descriptor `fd`. Return the
        number of bytes written.

        The file descriptor must be in non-blocking mode.
        """
        hub, event = None, None
        while True:
            try:
                return _write(fd, buf)
            except OSError as e:
                if e.errno not in ignored_errors:
                    raise
                if not PY3:
                    sys.exc_clear()
            if hub is None:
                hub = get_hub()
                event = hub.loop.io(fd, 2)
            hub.wait(event)


def tp_read(fd, n):
    """Read up to `n` bytes from file descriptor `fd`. Return a string
    containing the bytes read. If end-of-file is reached, an empty string
    is returned."""
    return get_hub().threadpool.apply(_read, (fd, n))


def tp_write(fd, buf):
    """Write bytes from buffer `buf` to file descriptor `fd`. Return the
    number of bytes written."""
    return get_hub().threadpool.apply(_write, (fd, buf))


if hasattr(os, 'fork'):
    _fork = os.fork

    def fork():
        result = _fork()
        if not result:
            reinit()
        return result

    if hasattr(os, 'WNOWAIT') or hasattr(os, 'WNOHANG'):
        # We can only do this on POSIX
        import time

        _waitpid = os.waitpid
        _WNOHANG = os.WNOHANG

        # {pid -> watcher or tuple(pid, rstatus, timestamp)}
        _watched_children = {}

        def _on_child(watcher, callback):
            # XXX: Could handle tracing here by not stopping
            # until the pid is terminated
            watcher.stop()
            _watched_children[watcher.pid] = (watcher.pid, watcher.rstatus, time.time())
            if callback:
                callback(watcher)
            # now is as good a time as any to reap children
            _reap_children()

        def _reap_children(timeout=60):
            # Remove all the dead children that haven't been waited on
            # for the *timeout*
            now = time.time()
            oldest_allowed = now - timeout
            for pid in _watched_children.keys():
                val = _watched_children[pid]
                if isinstance(val, tuple) and val[2] < oldest_allowed:
                    del _watched_children[pid]

        def waitpid(pid, options):
            # XXX Does not handle tracing children
            if pid <= 0:
                # magic functions for multiple children. Pass.
                return _waitpid(pid, options)

            if pid in _watched_children:
                # yes, we're watching it
                if options & _WNOHANG or isinstance(_watched_children[pid], tuple):
                    # We're either asked not to block, or it already finished, in which
                    # case blocking doesn't matter
                    result = _watched_children[pid]
                    if isinstance(result, tuple):
                        # it finished. libev child watchers
                        # are one-shot
                        del _watched_children[pid]
                        return result[:2]
                    # it's not finished
                    return (0, 0)
                else:
                    # we should block. Let the underlying OS call block; it should
                    # eventually die with OSError, depending on signal delivery
                    try:
                        return _waitpid(pid, options)
                    except OSError:
                        if pid in _watched_children and isinstance(_watched_children, tuple):
                            result = _watched_children[pid]
                            del _watched_children[pid]
                            return result[:2]
                        raise
            # we're not watching it
            return _waitpid(pid, options)

        def fork_and_watch(callback=None, loop=None, ref=False, fork=fork):
            """
            Fork a child process and start a child watcher for it in the parent process.

            This call cooperates with the :func:`gevent.os.waitpid` to enable cooperatively waiting
            for children to finish.

            :keyword callback: If given, a callable that will be called with the child watcher
                when the child finishes.
            :keyword loop: The loop to start the watcher in. Defaults to the
                loop of the current hub.
            :keyword fork: The fork function. Defaults to the one defined in this
                module (which automatically calls :func:`gevent.hub.reinit`).
                Pass the builtin :func:`os.fork` function if you do not need to
                initialize gevent in the child process.

            .. versionadded: 1.1a3
            """
            pid = fork()
            if pid:
                # parent
                loop = loop or get_hub().loop
                watcher = loop.child(pid)
                _watched_children[pid] = watcher
                watcher.start(_on_child, watcher, callback)
            return pid

        # Watch children by default
        fork = fork_and_watch

        __extensions__.append('fork_and_watch')
        __implements__.append("waitpid")

else:
    __implements__.remove('fork')


__all__ = __implements__ + __extensions__
