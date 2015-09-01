"""
Low-level operating system functions from :mod:`os`.

Cooperative I/O
===============

This module provides cooperative versions of :func:`os.read` and
:func:`os.write`. These functions are *not* monkey-patched; you
must explicitly call them or monkey patch them yourself.

POSIX functions
---------------

On POSIX, non-blocking IO is available.

- :func:`nb_read`
- :func:`nb_write`
- :func:`make_nonblocking`

All Platforms
-------------

On non-POSIX platforms (e.g., Windows), non-blocking IO is not
available. On those platforms (and on POSIX), cooperative IO can
be done with the threadpool.

- :func:`tp_read`
- :func:`tb_write`

Child Processes
===============

The functions :func:`fork` and (on POSIX) :func:`waitpid` can be used
to manage child processes.

.. warning::

   Forking a process that uses greenlets does not eliminate all non-running
   greenlets. Any that were scheduled in the hub of the forking thread in the parent
   remain scheduled in the child; compare this to how normal threads operate. (This behaviour
   may change is a subsequent major release.)
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
        """Put the file descriptor *fd* into non-blocking mode if possible.

        :return: A boolean value that evaluates to True if successful."""
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
    """Read up to *n* bytes from file descriptor *fd*. Return a string
    containing the bytes read. If end-of-file is reached, an empty string
    is returned.

    Reading is done using the threadpool.
    """
    return get_hub().threadpool.apply(_read, (fd, n))


def tp_write(fd, buf):
    """Write bytes from buffer *buf* to file descriptor *fd*. Return the
    number of bytes written.

    Writing is done using the threadpool.
    """
    return get_hub().threadpool.apply(_write, (fd, buf))


if hasattr(os, 'fork'):
    _raw_fork = os.fork

    def fork_gevent():
        """
        Forks the process using :func:`os.fork` and prepares the
        child process to continue using gevent before returning.

        .. note::

            The PID returned by this function may not be
            waitable with either :func:`os.waitpid` or :func:`waitpid`
            if libev child watchers are in use. For example, the
            :mod:`gevent.subprocess` module uses libev child watchers
            (which parts of gevent use libev child watchers is subject to change
            at any time). Most applications should use :func:`fork_and_watch`,
            which is monkey-patched as the default replacement for :func:`os.fork`
            and implements the ``fork`` function of this module by default, unless
            the environment variable ``GEVENT_NOWAITPID`` is defined before this
            module is imported.

        .. versionadded:: 1.1b2
        """
        result = _raw_fork()
        if not result:
            reinit()
        return result

    def fork():
        """
        A wrapper for :func:`fork_gevent` for non-POSIX platforms.
        """
        return fork_gevent()

    if hasattr(os, 'WNOWAIT') or hasattr(os, 'WNOHANG'):
        # We can only do this on POSIX
        import time

        _waitpid = os.waitpid
        _WNOHANG = os.WNOHANG

        _on_child_hook = lambda: None

        # {pid -> watcher or tuple(pid, rstatus, timestamp)}
        _watched_children = {}

        def _on_child(watcher, callback):
            # XXX: Could handle tracing here by not stopping
            # until the pid is terminated
            watcher.stop()
            _watched_children[watcher.pid] = (watcher.pid, watcher.rstatus, time.time())
            if callback:
                callback(watcher)
            # dispatch an "event"; used by gevent.signal.signal
            _on_child_hook()
            # now is as good a time as any to reap children
            _reap_children()

        def _reap_children(timeout=60):
            # Remove all the dead children that haven't been waited on
            # for the *timeout* seconds.
            # Some platforms queue delivery of SIGCHLD for all children that die;
            # in that case, a well-behaved application should call waitpid() for each
            # signal.
            # Some platforms (linux) only guarantee one delivery if multiple children
            # die. On that platform, the well-behave application calls waitpid() in a loop
            # until it gets back -1, indicating no more dead children need to be waited for.
            # In either case, waitpid should be called the same number of times as dead children,
            # thus removing all the watchers when a SIGCHLD arrives. The (generous) timeout
            # is to work with applications that neglect to call waitpid and prevent "unlimited"
            # growth.
            # Note that we don't watch for the case of pid wraparound. That is, we fork a new
            # child with the same pid as an existing watcher, but the child is already dead,
            # just not waited on yet.
            now = time.time()
            oldest_allowed = now - timeout
            dead = [pid for pid, val
                    in _watched_children.items()
                    if isinstance(val, tuple) and val[2] < oldest_allowed]
            for pid in dead:
                del _watched_children[pid]

        def waitpid(pid, options):
            """
            Wait for a child process to finish.

            If the child process was spawned using :func:`fork_and_watch`, then this
            function behaves cooperatively. If not, it *may* have race conditions; see
            :func:`fork_gevent` for more information.

            The arguments are as for the underlying :func:`os.waitpid`. Some combinations
            of *options* may not be supported (as of 1.1 that includes WUNTRACED).

            Availability: POSIX.

            .. versionadded:: 1.1a3
            """
            # XXX Does not handle tracing children
            if pid <= 0:
                # magic functions for multiple children.
                if pid == -1:
                    # Any child. If we have one that we're watching and that finished,
                    # we need to use that one. Otherwise, let the OS take care of it.
                    for k, v in _watched_children.items():
                        if isinstance(v, tuple):
                            pid = k
                            break
                if pid <= 0:
                    # If we didn't find anything, go to the OS. Otherwise,
                    # handle waiting
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

        def fork_and_watch(callback=None, loop=None, ref=False, fork=fork_gevent):
            """
            Fork a child process and start a child watcher for it in the parent process.

            This call cooperates with :func:`waitpid` to enable cooperatively waiting
            for children to finish. When monkey-patching, these functions are patched in as
            :func:`os.fork` and :func:`os.waitpid`, respectively.

            In the child process, this function calls :func:`gevent.hub.reinit` before returning.

            Availability: POSIX.

            :keyword callback: If given, a callable that will be called with the child watcher
                when the child finishes.
            :keyword loop: The loop to start the watcher in. Defaults to the
                loop of the current hub.
            :keyword fork: The fork function. Defaults to :func:`the one defined in this
                module <gevent_fork>` (which automatically calls :func:`gevent.hub.reinit`).
                Pass the builtin :func:`os.fork` function if you do not need to
                initialize gevent in the child process.

            .. versionadded:: 1.1a3
            """
            pid = fork()
            if pid:
                # parent
                loop = loop or get_hub().loop
                watcher = loop.child(pid)
                _watched_children[pid] = watcher
                watcher.start(_on_child, watcher, callback)
            return pid

        __extensions__.append('fork_and_watch')
        __extensions__.append('fork_gevent')

        # Watch children by default
        if not os.getenv('GEVENT_NOWAITPID'):
            def fork(*args, **kwargs):
                """
                Forks a child process and starts a child watcher for it in the
                parent process.

                This implementation of ``fork`` is a wrapper for :func:`fork_and_watch`
                when the environment variable ``GEVENT_NOWAITPID`` is *not* defined.
                This is the default and should be used by most applications.

                .. versionchanged:: 1.1b2
                """
                # take any args to match fork_and_watch
                return fork_and_watch(*args, **kwargs)
            __implements__.append("waitpid")
        else:
            def fork():
                """
                Forks a child process, initializes gevent in the child,
                but *does not* prepare the parent to wait for the child.

                This implementation of ``fork`` is a wrapper for :func:`fork_gevent`
                when the environment variable ``GEVENT_NOWAITPID`` *is* defined.
                This is not recommended for most applications.
                """
                return fork_gevent()
            __extensions__.append("waitpid")

else:
    __implements__.remove('fork')


__all__ = __implements__ + __extensions__
