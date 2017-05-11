"""
Cooperative ``subprocess`` module.

.. caution:: On POSIX platforms, this module is not usable from native
   threads other than the main thread; attempting to do so will raise
   a :exc:`TypeError`. This module depends on libev's fork watchers.
   On POSIX systems, fork watchers are implemented using signals, and
   the thread to which process-directed signals are delivered `is not
   defined`_. Because each native thread has its own gevent/libev
   loop, this means that a fork watcher registered with one loop
   (thread) may never see the signal about a child it spawned if the
   signal is sent to a different thread.

.. note:: The interface of this module is intended to match that of
   the standard library :mod:`subprocess` module (with many backwards
   compatible extensions from Python 3 backported to Python 2). There
   are some small differences between the Python 2 and Python 3
   versions of that module (the Python 2 ``TimeoutExpired`` exception,
   notably, extends ``Timeout`` and there is no ``SubprocessError``) and between the
   POSIX and Windows versions. The HTML documentation here can only
   describe one version; for definitive documentation, see the
   standard library or the source code.

.. _is not defined: http://www.linuxprogrammingblog.com/all-about-linux-signals?page=11
"""
from __future__ import absolute_import, print_function
# Can we split this up to make it cleaner? See https://github.com/gevent/gevent/issues/748
# pylint: disable=too-many-lines
# Import magic
# pylint: disable=undefined-all-variable,undefined-variable
# Most of this we inherit from the standard lib
# pylint: disable=bare-except,too-many-locals,too-many-statements,attribute-defined-outside-init
# pylint: disable=too-many-branches,too-many-instance-attributes
# Most of this is cross-platform
# pylint: disable=no-member,expression-not-assigned,unused-argument,unused-variable
import errno
import gc
import os
import signal
import sys
import traceback
from gevent.event import AsyncResult
from gevent.hub import get_hub, linkproxy, sleep, getcurrent
from gevent._compat import integer_types, string_types, xrange
from gevent._compat import PY3
from gevent._compat import reraise
from gevent._util import _NONE
from gevent._util import copy_globals
from gevent.fileobject import FileObject
from gevent.greenlet import Greenlet, joinall
spawn = Greenlet.spawn
import subprocess as __subprocess__


# Standard functions and classes that this module re-implements in a gevent-aware way.
__implements__ = [
    'Popen',
    'call',
    'check_call',
    'check_output',
]
if PY3 and not sys.platform.startswith('win32'):
    __implements__.append("_posixsubprocess")
    _posixsubprocess = None

# Some symbols we define that we expect to export;
# useful for static analysis
PIPE = "PIPE should be imported"

# Standard functions and classes that this module re-imports.
__imports__ = [
    'PIPE',
    'STDOUT',
    'CalledProcessError',
    # Windows:
    'CREATE_NEW_CONSOLE',
    'CREATE_NEW_PROCESS_GROUP',
    'STD_INPUT_HANDLE',
    'STD_OUTPUT_HANDLE',
    'STD_ERROR_HANDLE',
    'SW_HIDE',
    'STARTF_USESTDHANDLES',
    'STARTF_USESHOWWINDOW',
]


__extra__ = [
    'MAXFD',
    '_eintr_retry_call',
    'STARTUPINFO',
    'pywintypes',
    'list2cmdline',
    '_subprocess',
    '_winapi',
    # Python 2.5 does not have _subprocess, so we don't use it
    # XXX We don't run on Py 2.5 anymore; can/could/should we use _subprocess?
    # It's only used on mswindows
    'WAIT_OBJECT_0',
    'WaitForSingleObject',
    'GetExitCodeProcess',
    'GetStdHandle',
    'CreatePipe',
    'DuplicateHandle',
    'GetCurrentProcess',
    'DUPLICATE_SAME_ACCESS',
    'GetModuleFileName',
    'GetVersion',
    'CreateProcess',
    'INFINITE',
    'TerminateProcess',

    # These were added for 3.5, but we make them available everywhere.
    'run',
    'CompletedProcess',
]

if sys.version_info[:2] >= (3, 3):
    __imports__ += [
        'DEVNULL',
        'getstatusoutput',
        'getoutput',
        'SubprocessError',
        'TimeoutExpired',
    ]
else:
    __extra__.append("TimeoutExpired")


if sys.version_info[:2] >= (3, 5):
    __extra__.remove('run')
    __extra__.remove('CompletedProcess')
    __implements__.append('run')
    __implements__.append('CompletedProcess')

    # Removed in Python 3.5; this is the exact code that was removed:
    # https://hg.python.org/cpython/rev/f98b0a5e5ef5
    __extra__.remove('MAXFD')
    try:
        MAXFD = os.sysconf("SC_OPEN_MAX")
    except:
        MAXFD = 256

if sys.version_info[:2] >= (3, 6):
    # This was added to __all__ for windows in 3.6
    __extra__.remove('STARTUPINFO')
    __imports__.append('STARTUPINFO')

actually_imported = copy_globals(__subprocess__, globals(),
                                 only_names=__imports__,
                                 ignore_missing_names=True)
# anything we couldn't import from here we may need to find
# elsewhere
__extra__.extend(set(__imports__).difference(set(actually_imported)))
__imports__ = actually_imported
del actually_imported


# In Python 3 on Windows, a lot of the functions previously
# in _subprocess moved to _winapi
_subprocess = getattr(__subprocess__, '_subprocess', _NONE)
_winapi = getattr(__subprocess__, '_winapi', _NONE)

_attr_resolution_order = [__subprocess__, _subprocess, _winapi]

for name in list(__extra__):
    if name in globals():
        continue
    value = _NONE
    for place in _attr_resolution_order:
        value = getattr(place, name, _NONE)
        if value is not _NONE:
            break

    if value is _NONE:
        __extra__.remove(name)
    else:
        globals()[name] = value

del _attr_resolution_order
__all__ = __implements__ + __imports__
# Some other things we want to document
for _x in ('run', 'CompletedProcess', 'TimeoutExpired'):
    if _x not in __all__:
        __all__.append(_x)


mswindows = sys.platform == 'win32'
if mswindows:
    import msvcrt # pylint: disable=import-error
    if PY3:
        class Handle(int):
            closed = False

            def Close(self):
                if not self.closed:
                    self.closed = True
                    _winapi.CloseHandle(self)

            def Detach(self):
                if not self.closed:
                    self.closed = True
                    return int(self)
                raise ValueError("already closed")

            def __repr__(self):
                return "Handle(%d)" % int(self)

            __del__ = Close
            __str__ = __repr__
else:
    import fcntl
    import pickle
    from gevent import monkey
    fork = monkey.get_original('os', 'fork')
    from gevent.os import fork_and_watch

def call(*popenargs, **kwargs):
    """
    call(args, *, stdin=None, stdout=None, stderr=None, shell=False, timeout=None) -> returncode

    Run command with arguments. Wait for command to complete or
    timeout, then return the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example::

        retcode = call(["ls", "-l"])

    .. versionchanged:: 1.2a1
       The ``timeout`` keyword argument is now accepted on all supported
       versions of Python (not just Python 3) and if it expires will raise a
       :exc:`TimeoutExpired` exception (under Python 2 this is a subclass of :exc:`~.Timeout`).
    """
    timeout = kwargs.pop('timeout', None)
    with Popen(*popenargs, **kwargs) as p:
        try:
            return p.wait(timeout=timeout, _raise_exc=True)
        except:
            p.kill()
            p.wait()
            raise

def check_call(*popenargs, **kwargs):
    """
    check_call(args, *, stdin=None, stdout=None, stderr=None, shell=False, timeout=None) -> 0

    Run command with arguments.  Wait for command to complete.  If
    the exit code was zero then return, otherwise raise
    :exc:`CalledProcessError`.  The ``CalledProcessError`` object will have the
    return code in the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example::

        retcode = check_call(["ls", "-l"])
    """
    retcode = call(*popenargs, **kwargs)
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise CalledProcessError(retcode, cmd)
    return 0

def check_output(*popenargs, **kwargs):
    r"""
    check_output(args, *, input=None, stdin=None, stderr=None, shell=False, universal_newlines=False, timeout=None) -> output

    Run command with arguments and return its output.

    If the exit code was non-zero it raises a :exc:`CalledProcessError`.  The
    ``CalledProcessError`` object will have the return code in the returncode
    attribute and output in the output attribute.


    The arguments are the same as for the Popen constructor.  Example::

        >>> check_output(["ls", "-1", "/dev/null"])
        '/dev/null\n'

    The ``stdout`` argument is not allowed as it is used internally.

    To capture standard error in the result, use ``stderr=STDOUT``::

        >>> check_output(["/bin/sh", "-c",
        ...               "ls -l non_existent_file ; exit 0"],
        ...              stderr=STDOUT)
        'ls: non_existent_file: No such file or directory\n'

    There is an additional optional argument, "input", allowing you to
    pass a string to the subprocess's stdin.  If you use this argument
    you may not also use the Popen constructor's "stdin" argument, as
    it too will be used internally.  Example::

        >>> check_output(["sed", "-e", "s/foo/bar/"],
        ...              input=b"when in the course of fooman events\n")
        'when in the course of barman events\n'

    If ``universal_newlines=True`` is passed, the return value will be a
    string rather than bytes.

    .. versionchanged:: 1.2a1
       The ``timeout`` keyword argument is now accepted on all supported
       versions of Python (not just Python 3) and if it expires will raise a
       :exc:`TimeoutExpired` exception (under Python 2 this is a subclass of :exc:`~.Timeout`).
    .. versionchanged:: 1.2a1
       The ``input`` keyword argument is now accepted on all supported
       versions of Python, not just Python 3
    """
    timeout = kwargs.pop('timeout', None)
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    if 'input' in kwargs:
        if 'stdin' in kwargs:
            raise ValueError('stdin and input arguments may not both be used.')
        inputdata = kwargs['input']
        del kwargs['input']
        kwargs['stdin'] = PIPE
    else:
        inputdata = None
    with Popen(*popenargs, stdout=PIPE, **kwargs) as process:
        try:
            output, unused_err = process.communicate(inputdata, timeout=timeout)
        except TimeoutExpired:
            process.kill()
            output, unused_err = process.communicate()
            raise TimeoutExpired(process.args, timeout, output=output)
        except:
            process.kill()
            process.wait()
            raise
        retcode = process.poll()
        if retcode:
            raise CalledProcessError(retcode, process.args, output=output)
    return output

_PLATFORM_DEFAULT_CLOSE_FDS = object()

if 'TimeoutExpired' not in globals():
    # Python 2

    # Make TimeoutExpired inherit from _Timeout so it can be caught
    # the way we used to throw things (except Timeout), but make sure it doesn't
    # init a timer. Note that we can't have a fake 'SubprocessError' that inherits
    # from exception, because we need TimeoutExpired to just be a BaseException for
    # bwc.
    from gevent.timeout import Timeout as _Timeout

    class TimeoutExpired(_Timeout):
        """
        This exception is raised when the timeout expires while waiting for
        a child process in `communicate`.

        Under Python 2, this is a gevent extension with the same name as the
        Python 3 class for source-code forward compatibility. However, it extends
        :class:`gevent.timeout.Timeout` for backwards compatibility (because
        we used to just raise a plain ``Timeout``); note that ``Timeout`` is a
        ``BaseException``, *not* an ``Exception``.

        .. versionadded:: 1.2a1
        """
        def __init__(self, cmd, timeout, output=None):
            _Timeout.__init__(self, timeout, _use_timer=False)
            self.cmd = cmd
            self.timeout = timeout
            self.output = output

        def __str__(self):
            return ("Command '%s' timed out after %s seconds" %
                    (self.cmd, self.timeout))


class Popen(object):
    """
    The underlying process creation and management in this module is
    handled by the Popen class. It offers a lot of flexibility so that
    developers are able to handle the less common cases not covered by
    the convenience functions.

    .. seealso:: :class:`subprocess.Popen`
       This class should have the same interface as the standard library class.

    .. versionchanged:: 1.2a1
       Instances can now be used as context managers under Python 2.7. Previously
       this was restricted to Python 3.

    .. versionchanged:: 1.2a1
       Instances now save the ``args`` attribute under Python 2.7. Previously this was
       restricted to Python 3.
    """

    def __init__(self, args, bufsize=None, executable=None,
                 stdin=None, stdout=None, stderr=None,
                 preexec_fn=None, close_fds=_PLATFORM_DEFAULT_CLOSE_FDS, shell=False,
                 cwd=None, env=None, universal_newlines=False,
                 startupinfo=None, creationflags=0, threadpool=None,
                 **kwargs):
        """Create new Popen instance.

        :param kwargs: *Only* allowed under Python 3; under Python 2, any
          unrecognized keyword arguments will result in a :exc:`TypeError`.
          Under Python 3, keyword arguments can include ``pass_fds``, ``start_new_session``,
          ``restore_signals``, ``encoding`` and ``errors``

        .. versionchanged:: 1.2b1
           Add the ``encoding`` and ``errors`` parameters for Python 3.
        """

        if not PY3 and kwargs:
            raise TypeError("Got unexpected keyword arguments", kwargs)
        pass_fds = kwargs.pop('pass_fds', ())
        start_new_session = kwargs.pop('start_new_session', False)
        restore_signals = kwargs.pop('restore_signals', True)
        # Added in 3.6. These are kept as ivars
        encoding = self.encoding = kwargs.pop('encoding', None)
        errors = self.errors = kwargs.pop('errors', None)

        hub = get_hub()

        if bufsize is None:
            # bufsize has different defaults on Py3 and Py2
            if PY3:
                bufsize = -1
            else:
                bufsize = 0
        if not isinstance(bufsize, integer_types):
            raise TypeError("bufsize must be an integer")

        if mswindows:
            if preexec_fn is not None:
                raise ValueError("preexec_fn is not supported on Windows "
                                 "platforms")
            any_stdio_set = (stdin is not None or stdout is not None or
                             stderr is not None)
            if close_fds is _PLATFORM_DEFAULT_CLOSE_FDS:
                if any_stdio_set:
                    close_fds = False
                else:
                    close_fds = True
            elif close_fds and any_stdio_set:
                raise ValueError("close_fds is not supported on Windows "
                                 "platforms if you redirect stdin/stdout/stderr")
            if threadpool is None:
                threadpool = hub.threadpool
            self.threadpool = threadpool
            self._waiting = False
        else:
            # POSIX
            if close_fds is _PLATFORM_DEFAULT_CLOSE_FDS:
                # close_fds has different defaults on Py3/Py2
                if PY3: # pylint: disable=simplifiable-if-statement
                    close_fds = True
                else:
                    close_fds = False

            if pass_fds and not close_fds:
                import warnings
                warnings.warn("pass_fds overriding close_fds.", RuntimeWarning)
                close_fds = True
            if startupinfo is not None:
                raise ValueError("startupinfo is only supported on Windows "
                                 "platforms")
            if creationflags != 0:
                raise ValueError("creationflags is only supported on Windows "
                                 "platforms")
            assert threadpool is None
            self._loop = hub.loop

        self.args = args # Previously this was Py3 only.
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.pid = None
        self.returncode = None
        self.universal_newlines = universal_newlines
        self.result = AsyncResult()

        # Input and output objects. The general principle is like
        # this:
        #
        # Parent                   Child
        # ------                   -----
        # p2cwrite   ---stdin--->  p2cread
        # c2pread    <--stdout---  c2pwrite
        # errread    <--stderr---  errwrite
        #
        # On POSIX, the child objects are file descriptors.  On
        # Windows, these are Windows file handles.  The parent objects
        # are file descriptors on both platforms.  The parent objects
        # are None when not using PIPEs. The child objects are None
        # when not redirecting.

        (p2cread, p2cwrite,
         c2pread, c2pwrite,
         errread, errwrite) = self._get_handles(stdin, stdout, stderr)

        # We wrap OS handles *before* launching the child, otherwise a
        # quickly terminating child could make our fds unwrappable
        # (see #8458).
        if mswindows:
            if p2cwrite is not None:
                p2cwrite = msvcrt.open_osfhandle(p2cwrite.Detach(), 0)
            if c2pread is not None:
                c2pread = msvcrt.open_osfhandle(c2pread.Detach(), 0)
            if errread is not None:
                errread = msvcrt.open_osfhandle(errread.Detach(), 0)

        text_mode = PY3 and (self.encoding or self.errors or universal_newlines)

        if p2cwrite is not None:
            if PY3 and text_mode:
                # Under Python 3, if we left on the 'b' we'd get different results
                # depending on whether we used FileObjectPosix or FileObjectThread
                self.stdin = FileObject(p2cwrite, 'wb', bufsize)
                self.stdin.translate_newlines(None,
                                              write_through=True,
                                              line_buffering=(bufsize == 1),
                                              encoding=self.encoding, errors=self.errors)
            else:
                self.stdin = FileObject(p2cwrite, 'wb', bufsize)
        if c2pread is not None:
            if universal_newlines or text_mode:
                if PY3:
                    # FileObjectThread doesn't support the 'U' qualifier
                    # with a bufsize of 0
                    self.stdout = FileObject(c2pread, 'rb', bufsize)
                    # NOTE: Universal Newlines are broken on Windows/Py3, at least
                    # in some cases. This is true in the stdlib subprocess module
                    # as well; the following line would fix the test cases in
                    # test__subprocess.py that depend on python_universal_newlines,
                    # but would be inconsistent with the stdlib:
                    #msvcrt.setmode(self.stdout.fileno(), os.O_TEXT)
                    self.stdout.translate_newlines('r', encoding=self.encoding, errors=self.errors)
                else:
                    self.stdout = FileObject(c2pread, 'rU', bufsize)
            else:
                self.stdout = FileObject(c2pread, 'rb', bufsize)
        if errread is not None:
            if universal_newlines or text_mode:
                if PY3:
                    self.stderr = FileObject(errread, 'rb', bufsize)
                    self.stderr.translate_newlines(None, encoding=encoding, errors=errors)
                else:
                    self.stderr = FileObject(errread, 'rU', bufsize)
            else:
                self.stderr = FileObject(errread, 'rb', bufsize)

        self._closed_child_pipe_fds = False
        try:
            self._execute_child(args, executable, preexec_fn, close_fds,
                                pass_fds, cwd, env, universal_newlines,
                                startupinfo, creationflags, shell,
                                p2cread, p2cwrite,
                                c2pread, c2pwrite,
                                errread, errwrite,
                                restore_signals, start_new_session)
        except:
            # Cleanup if the child failed starting.
            # (gevent: New in python3, but reported as gevent bug in #347.
            # Note that under Py2, any error raised below will replace the
            # original error so we have to use reraise)
            if not PY3:
                exc_info = sys.exc_info()
            for f in filter(None, (self.stdin, self.stdout, self.stderr)):
                try:
                    f.close()
                except (OSError, IOError):
                    pass  # Ignore EBADF or other errors.

            if not self._closed_child_pipe_fds:
                to_close = []
                if stdin == PIPE:
                    to_close.append(p2cread)
                if stdout == PIPE:
                    to_close.append(c2pwrite)
                if stderr == PIPE:
                    to_close.append(errwrite)
                if hasattr(self, '_devnull'):
                    to_close.append(self._devnull)
                for fd in to_close:
                    try:
                        os.close(fd)
                    except (OSError, IOError):
                        pass
            if not PY3:
                try:
                    reraise(*exc_info)
                finally:
                    del exc_info
            raise

    def __repr__(self):
        return '<%s at 0x%x pid=%r returncode=%r>' % (self.__class__.__name__, id(self), self.pid, self.returncode)

    def _on_child(self, watcher):
        watcher.stop()
        status = watcher.rstatus
        if os.WIFSIGNALED(status):
            self.returncode = -os.WTERMSIG(status)
        else:
            self.returncode = os.WEXITSTATUS(status)
        self.result.set(self.returncode)

    def _get_devnull(self):
        if not hasattr(self, '_devnull'):
            self._devnull = os.open(os.devnull, os.O_RDWR)
        return self._devnull

    _stdout_buffer = None
    _stderr_buffer = None

    def communicate(self, input=None, timeout=None):
        """Interact with process: Send data to stdin.  Read data from
        stdout and stderr, until end-of-file is reached.  Wait for
        process to terminate.  The optional input argument should be a
        string to be sent to the child process, or None, if no data
        should be sent to the child.

        communicate() returns a tuple (stdout, stderr).

        :keyword timeout: Under Python 2, this is a gevent extension; if
           given and it expires, we will raise :exc:`TimeoutExpired`, which
           extends :exc:`gevent.timeout.Timeout` (note that this only extends :exc:`BaseException`,
           *not* :exc:`Exception`)
           Under Python 3, this raises the standard :exc:`TimeoutExpired` exception.

        .. versionchanged:: 1.1a2
           Under Python 2, if the *timeout* elapses, raise the :exc:`gevent.timeout.Timeout`
           exception. Previously, we silently returned.
        .. versionchanged:: 1.1b5
           Honor a *timeout* even if there's no way to communicate with the child
           (stdin, stdout, and stderr are not pipes).
        """
        greenlets = []
        if self.stdin:
            greenlets.append(spawn(write_and_close, self.stdin, input))

        # If the timeout parameter is used, and the caller calls back after
        # getting a TimeoutExpired exception, we can wind up with multiple
        # greenlets trying to run and read from and close stdout/stderr.
        # That's bad because it can lead to 'RuntimeError: reentrant call in io.BufferedReader'.
        # We can't just kill the previous greenlets when a timeout happens,
        # though, because we risk losing the output collected by that greenlet
        # (and Python 3, where timeout is an official parameter, explicitly says
        # that no output should be lost in the event of a timeout.) Instead, we're
        # watching for the exception and ignoring it. It's not elegant,
        # but it works
        if self.stdout:
            def _read_out():
                try:
                    data = self.stdout.read()
                except RuntimeError:
                    return
                if self._stdout_buffer is not None:
                    self._stdout_buffer += data
                else:
                    self._stdout_buffer = data
            stdout = spawn(_read_out)
            greenlets.append(stdout)
        else:
            stdout = None

        if self.stderr:
            def _read_err():
                try:
                    data = self.stderr.read()
                except RuntimeError:
                    return
                if self._stderr_buffer is not None:
                    self._stderr_buffer += data
                else:
                    self._stderr_buffer = data
            stderr = spawn(_read_err)
            greenlets.append(stderr)
        else:
            stderr = None

        # If we were given stdin=stdout=stderr=None, we have no way to
        # communicate with the child, and thus no greenlets to wait
        # on. This is a nonsense case, but it comes up in the test
        # case for Python 3.5 (test_subprocess.py
        # RunFuncTestCase.test_timeout). Instead, we go directly to
        # self.wait
        if not greenlets and timeout is not None:
            self.wait(timeout=timeout, _raise_exc=True)

        done = joinall(greenlets, timeout=timeout)
        if timeout is not None and len(done) != len(greenlets):
            raise TimeoutExpired(self.args, timeout)

        if self.stdout:
            try:
                self.stdout.close()
            except RuntimeError:
                pass
        if self.stderr:
            try:
                self.stderr.close()
            except RuntimeError:
                pass
        self.wait()
        stdout_value = self._stdout_buffer
        self._stdout_buffer = None
        stderr_value = self._stderr_buffer
        self._stderr_buffer = None
        # XXX: Under python 3 in universal newlines mode we should be
        # returning str, not bytes
        return (None if stdout is None else stdout_value or b'',
                None if stderr is None else stderr_value or b'')

    def poll(self):
        """Check if child process has terminated. Set and return :attr:`returncode` attribute."""
        return self._internal_poll()

    def __enter__(self):
        return self

    def __exit__(self, t, v, tb):
        if self.stdout:
            self.stdout.close()
        if self.stderr:
            self.stderr.close()
        try:  # Flushing a BufferedWriter may raise an error
            if self.stdin:
                self.stdin.close()
        finally:
            # Wait for the process to terminate, to avoid zombies.
            # JAM: gevent: If the process never terminates, this
            # blocks forever.
            self.wait()

    def _gevent_result_wait(self, timeout=None, raise_exc=PY3):
        result = self.result.wait(timeout=timeout)
        if raise_exc and timeout is not None and not self.result.ready():
            raise TimeoutExpired(self.args, timeout)
        return result


    if mswindows:
        #
        # Windows methods
        #
        def _get_handles(self, stdin, stdout, stderr):
            """Construct and return tuple with IO objects:
            p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
            """
            if stdin is None and stdout is None and stderr is None:
                return (None, None, None, None, None, None)

            p2cread, p2cwrite = None, None
            c2pread, c2pwrite = None, None
            errread, errwrite = None, None

            try:
                DEVNULL
            except NameError:
                _devnull = object()
            else:
                _devnull = DEVNULL

            if stdin is None:
                p2cread = GetStdHandle(STD_INPUT_HANDLE)
                if p2cread is None:
                    p2cread, _ = CreatePipe(None, 0)
                    if PY3:
                        p2cread = Handle(p2cread)
                        _winapi.CloseHandle(_)
            elif stdin == PIPE:
                p2cread, p2cwrite = CreatePipe(None, 0)
                if PY3:
                    p2cread, p2cwrite = Handle(p2cread), Handle(p2cwrite)
            elif stdin == _devnull:
                p2cread = msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stdin, int):
                p2cread = msvcrt.get_osfhandle(stdin)
            else:
                # Assuming file-like object
                p2cread = msvcrt.get_osfhandle(stdin.fileno())
            p2cread = self._make_inheritable(p2cread)

            if stdout is None:
                c2pwrite = GetStdHandle(STD_OUTPUT_HANDLE)
                if c2pwrite is None:
                    _, c2pwrite = CreatePipe(None, 0)
                    if PY3:
                        c2pwrite = Handle(c2pwrite)
                        _winapi.CloseHandle(_)
            elif stdout == PIPE:
                c2pread, c2pwrite = CreatePipe(None, 0)
                if PY3:
                    c2pread, c2pwrite = Handle(c2pread), Handle(c2pwrite)
            elif stdout == _devnull:
                c2pwrite = msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stdout, int):
                c2pwrite = msvcrt.get_osfhandle(stdout)
            else:
                # Assuming file-like object
                c2pwrite = msvcrt.get_osfhandle(stdout.fileno())
            c2pwrite = self._make_inheritable(c2pwrite)

            if stderr is None:
                errwrite = GetStdHandle(STD_ERROR_HANDLE)
                if errwrite is None:
                    _, errwrite = CreatePipe(None, 0)
                    if PY3:
                        errwrite = Handle(errwrite)
                        _winapi.CloseHandle(_)
            elif stderr == PIPE:
                errread, errwrite = CreatePipe(None, 0)
                if PY3:
                    errread, errwrite = Handle(errread), Handle(errwrite)
            elif stderr == STDOUT:
                errwrite = c2pwrite
            elif stderr == _devnull:
                errwrite = msvcrt.get_osfhandle(self._get_devnull())
            elif isinstance(stderr, int):
                errwrite = msvcrt.get_osfhandle(stderr)
            else:
                # Assuming file-like object
                errwrite = msvcrt.get_osfhandle(stderr.fileno())
            errwrite = self._make_inheritable(errwrite)

            return (p2cread, p2cwrite,
                    c2pread, c2pwrite,
                    errread, errwrite)

        def _make_inheritable(self, handle):
            """Return a duplicate of handle, which is inheritable"""
            return DuplicateHandle(GetCurrentProcess(),
                                   handle, GetCurrentProcess(), 0, 1,
                                   DUPLICATE_SAME_ACCESS)

        def _find_w9xpopen(self):
            """Find and return absolute path to w9xpopen.exe"""
            w9xpopen = os.path.join(os.path.dirname(GetModuleFileName(0)),
                                    "w9xpopen.exe")
            if not os.path.exists(w9xpopen):
                # Eeek - file-not-found - possibly an embedding
                # situation - see if we can locate it in sys.exec_prefix
                w9xpopen = os.path.join(os.path.dirname(sys.exec_prefix),
                                        "w9xpopen.exe")
                if not os.path.exists(w9xpopen):
                    raise RuntimeError("Cannot locate w9xpopen.exe, which is "
                                       "needed for Popen to work with your "
                                       "shell or platform.")
            return w9xpopen

        def _execute_child(self, args, executable, preexec_fn, close_fds,
                           pass_fds, cwd, env, universal_newlines,
                           startupinfo, creationflags, shell,
                           p2cread, p2cwrite,
                           c2pread, c2pwrite,
                           errread, errwrite,
                           unused_restore_signals, unused_start_new_session):
            """Execute program (MS Windows version)"""

            assert not pass_fds, "pass_fds not supported on Windows."

            if not isinstance(args, string_types):
                args = list2cmdline(args)

            # Process startup details
            if startupinfo is None:
                startupinfo = STARTUPINFO()
            if None not in (p2cread, c2pwrite, errwrite):
                startupinfo.dwFlags |= STARTF_USESTDHANDLES
                startupinfo.hStdInput = p2cread
                startupinfo.hStdOutput = c2pwrite
                startupinfo.hStdError = errwrite

            if shell:
                startupinfo.dwFlags |= STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = SW_HIDE
                comspec = os.environ.get("COMSPEC", "cmd.exe")
                args = '{} /c "{}"'.format(comspec, args)
                if GetVersion() >= 0x80000000 or os.path.basename(comspec).lower() == "command.com":
                    # Win9x, or using command.com on NT. We need to
                    # use the w9xpopen intermediate program. For more
                    # information, see KB Q150956
                    # (http://web.archive.org/web/20011105084002/http://support.microsoft.com/support/kb/articles/Q150/9/56.asp)
                    w9xpopen = self._find_w9xpopen()
                    args = '"%s" %s' % (w9xpopen, args)
                    # Not passing CREATE_NEW_CONSOLE has been known to
                    # cause random failures on win9x.  Specifically a
                    # dialog: "Your program accessed mem currently in
                    # use at xxx" and a hopeful warning about the
                    # stability of your system.  Cost is Ctrl+C wont
                    # kill children.
                    creationflags |= CREATE_NEW_CONSOLE

            # Start the process
            try:
                hp, ht, pid, tid = CreateProcess(executable, args,
                                                 # no special security
                                                 None, None,
                                                 int(not close_fds),
                                                 creationflags,
                                                 env,
                                                 cwd,
                                                 startupinfo)
            except IOError as e: # From 2.6 on, pywintypes.error was defined as IOError
                # Translate pywintypes.error to WindowsError, which is
                # a subclass of OSError.  FIXME: We should really
                # translate errno using _sys_errlist (or similar), but
                # how can this be done from Python?
                if PY3:
                    raise # don't remap here
                raise WindowsError(*e.args)
            finally:
                # Child is launched. Close the parent's copy of those pipe
                # handles that only the child should have open.  You need
                # to make sure that no handles to the write end of the
                # output pipe are maintained in this process or else the
                # pipe will not close when the child process exits and the
                # ReadFile will hang.
                def _close(x):
                    if x is not None and x != -1:
                        if hasattr(x, 'Close'):
                            x.Close()
                        else:
                            _winapi.CloseHandle(x)

                _close(p2cread)
                _close(c2pwrite)
                _close(errwrite)
                if hasattr(self, '_devnull'):
                    os.close(self._devnull)

            # Retain the process handle, but close the thread handle
            self._child_created = True
            self._handle = Handle(hp) if not hasattr(hp, 'Close') else hp
            self.pid = pid
            _winapi.CloseHandle(ht) if not hasattr(ht, 'Close') else ht.Close()

        def _internal_poll(self):
            """Check if child process has terminated.  Returns returncode
            attribute.
            """
            if self.returncode is None:
                if WaitForSingleObject(self._handle, 0) == WAIT_OBJECT_0:
                    self.returncode = GetExitCodeProcess(self._handle)
                    self.result.set(self.returncode)
            return self.returncode

        def rawlink(self, callback):
            if not self.result.ready() and not self._waiting:
                self._waiting = True
                Greenlet.spawn(self._wait)
            self.result.rawlink(linkproxy(callback, self))
            # XXX unlink

        def _blocking_wait(self):
            WaitForSingleObject(self._handle, INFINITE)
            self.returncode = GetExitCodeProcess(self._handle)
            return self.returncode

        def _wait(self):
            self.threadpool.spawn(self._blocking_wait).rawlink(self.result)

        def wait(self, timeout=None, _raise_exc=PY3):
            """Wait for child process to terminate.  Returns returncode
            attribute."""
            if self.returncode is None:
                if not self._waiting:
                    self._waiting = True
                    self._wait()
            return self._gevent_result_wait(timeout, _raise_exc)

        def send_signal(self, sig):
            """Send a signal to the process
            """
            if sig == signal.SIGTERM:
                self.terminate()
            elif sig == signal.CTRL_C_EVENT:
                os.kill(self.pid, signal.CTRL_C_EVENT)
            elif sig == signal.CTRL_BREAK_EVENT:
                os.kill(self.pid, signal.CTRL_BREAK_EVENT)
            else:
                raise ValueError("Unsupported signal: {}".format(sig))

        def terminate(self):
            """Terminates the process
            """
            TerminateProcess(self._handle, 1)

        kill = terminate

    else:
        #
        # POSIX methods
        #

        def rawlink(self, callback):
            # Not public documented, part of the link protocol
            self.result.rawlink(linkproxy(callback, self))
        # XXX unlink

        def _get_handles(self, stdin, stdout, stderr):
            """Construct and return tuple with IO objects:
            p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
            """
            p2cread, p2cwrite = None, None
            c2pread, c2pwrite = None, None
            errread, errwrite = None, None

            try:
                DEVNULL
            except NameError:
                _devnull = object()
            else:
                _devnull = DEVNULL

            if stdin is None:
                pass
            elif stdin == PIPE:
                p2cread, p2cwrite = self.pipe_cloexec()
            elif stdin == _devnull:
                p2cread = self._get_devnull()
            elif isinstance(stdin, int):
                p2cread = stdin
            else:
                # Assuming file-like object
                p2cread = stdin.fileno()

            if stdout is None:
                pass
            elif stdout == PIPE:
                c2pread, c2pwrite = self.pipe_cloexec()
            elif stdout == _devnull:
                c2pwrite = self._get_devnull()
            elif isinstance(stdout, int):
                c2pwrite = stdout
            else:
                # Assuming file-like object
                c2pwrite = stdout.fileno()

            if stderr is None:
                pass
            elif stderr == PIPE:
                errread, errwrite = self.pipe_cloexec()
            elif stderr == STDOUT:
                errwrite = c2pwrite
            elif stderr == _devnull:
                errwrite = self._get_devnull()
            elif isinstance(stderr, int):
                errwrite = stderr
            else:
                # Assuming file-like object
                errwrite = stderr.fileno()

            return (p2cread, p2cwrite,
                    c2pread, c2pwrite,
                    errread, errwrite)

        def _set_cloexec_flag(self, fd, cloexec=True):
            try:
                cloexec_flag = fcntl.FD_CLOEXEC
            except AttributeError:
                cloexec_flag = 1

            old = fcntl.fcntl(fd, fcntl.F_GETFD)
            if cloexec:
                fcntl.fcntl(fd, fcntl.F_SETFD, old | cloexec_flag)
            else:
                fcntl.fcntl(fd, fcntl.F_SETFD, old & ~cloexec_flag)

        def _remove_nonblock_flag(self, fd):
            flags = fcntl.fcntl(fd, fcntl.F_GETFL) & (~os.O_NONBLOCK)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags)

        def pipe_cloexec(self):
            """Create a pipe with FDs set CLOEXEC."""
            # Pipes' FDs are set CLOEXEC by default because we don't want them
            # to be inherited by other subprocesses: the CLOEXEC flag is removed
            # from the child's FDs by _dup2(), between fork() and exec().
            # This is not atomic: we would need the pipe2() syscall for that.
            r, w = os.pipe()
            self._set_cloexec_flag(r)
            self._set_cloexec_flag(w)
            return r, w

        def _close_fds(self, keep):
            # `keep` is a set of fds, so we
            # use os.closerange from 3 to min(keep)
            # and then from max(keep + 1) to MAXFD and
            # loop through filling in the gaps.
            # Under new python versions, we need to explicitly set
            # passed fds to be inheritable or they will go away on exec
            if hasattr(os, 'set_inheritable'):
                set_inheritable = os.set_inheritable
            else:
                set_inheritable = lambda i, v: True
            if hasattr(os, 'closerange'):
                keep = sorted(keep)
                min_keep = min(keep)
                max_keep = max(keep)
                os.closerange(3, min_keep)
                os.closerange(max_keep + 1, MAXFD)
                for i in xrange(min_keep, max_keep):
                    if i in keep:
                        set_inheritable(i, True)
                        continue

                    try:
                        os.close(i)
                    except:
                        pass
            else:
                for i in xrange(3, MAXFD):
                    if i in keep:
                        set_inheritable(i, True)
                        continue
                    try:
                        os.close(i)
                    except:
                        pass

        def _execute_child(self, args, executable, preexec_fn, close_fds,
                           pass_fds, cwd, env, universal_newlines,
                           startupinfo, creationflags, shell,
                           p2cread, p2cwrite,
                           c2pread, c2pwrite,
                           errread, errwrite,
                           restore_signals, start_new_session):
            """Execute program (POSIX version)"""

            if PY3 and isinstance(args, (str, bytes)):
                args = [args]
            elif not PY3 and isinstance(args, string_types):
                args = [args]
            else:
                args = list(args)

            if shell:
                args = ["/bin/sh", "-c"] + args
                if executable:
                    args[0] = executable

            if executable is None:
                executable = args[0]

            self._loop.install_sigchld()

            # For transferring possible exec failure from child to parent
            # The first char specifies the exception type: 0 means
            # OSError, 1 means some other error.
            errpipe_read, errpipe_write = self.pipe_cloexec()
            # errpipe_write must not be in the standard io 0, 1, or 2 fd range.
            low_fds_to_close = []
            while errpipe_write < 3:
                low_fds_to_close.append(errpipe_write)
                errpipe_write = os.dup(errpipe_write)
            for low_fd in low_fds_to_close:
                os.close(low_fd)
            try:
                try:
                    gc_was_enabled = gc.isenabled()
                    # Disable gc to avoid bug where gc -> file_dealloc ->
                    # write to stderr -> hang.  http://bugs.python.org/issue1336
                    gc.disable()
                    try:
                        self.pid = fork_and_watch(self._on_child, self._loop, True, fork)
                    except:
                        if gc_was_enabled:
                            gc.enable()
                        raise
                    if self.pid == 0:
                        # Child
                        try:
                            # Close parent's pipe ends
                            if p2cwrite is not None:
                                os.close(p2cwrite)
                            if c2pread is not None:
                                os.close(c2pread)
                            if errread is not None:
                                os.close(errread)
                            os.close(errpipe_read)

                            # When duping fds, if there arises a situation
                            # where one of the fds is either 0, 1 or 2, it
                            # is possible that it is overwritten (#12607).
                            if c2pwrite == 0:
                                c2pwrite = os.dup(c2pwrite)
                            if errwrite == 0 or errwrite == 1:
                                errwrite = os.dup(errwrite)

                            # Dup fds for child
                            def _dup2(a, b):
                                # dup2() removes the CLOEXEC flag but
                                # we must do it ourselves if dup2()
                                # would be a no-op (issue #10806).
                                if a == b:
                                    self._set_cloexec_flag(a, False)
                                elif a is not None:
                                    os.dup2(a, b)
                                self._remove_nonblock_flag(b)
                            _dup2(p2cread, 0)
                            _dup2(c2pwrite, 1)
                            _dup2(errwrite, 2)

                            # Close pipe fds.  Make sure we don't close the
                            # same fd more than once, or standard fds.
                            closed = set([None])
                            for fd in [p2cread, c2pwrite, errwrite]:
                                if fd not in closed and fd > 2:
                                    os.close(fd)
                                    closed.add(fd)

                            if cwd is not None:
                                os.chdir(cwd)

                            if preexec_fn:
                                preexec_fn()

                            # Close all other fds, if asked for. This must be done
                            # after preexec_fn runs.
                            if close_fds:
                                fds_to_keep = set(pass_fds)
                                fds_to_keep.add(errpipe_write)
                                self._close_fds(fds_to_keep)
                            elif hasattr(os, 'get_inheritable'):
                                # close_fds was false, and we're on
                                # Python 3.4 or newer, so "all file
                                # descriptors except standard streams
                                # are closed, and inheritable handles
                                # are only inherited if the close_fds
                                # parameter is False."
                                for i in xrange(3, MAXFD):
                                    try:
                                        if i == errpipe_write or os.get_inheritable(i):
                                            continue
                                        os.close(i)
                                    except:
                                        pass

                            if restore_signals:
                                # restore the documented signals back to sig_dfl;
                                # not all will be defined on every platform
                                for sig in 'SIGPIPE', 'SIGXFZ', 'SIGXFSZ':
                                    sig = getattr(signal, sig, None)
                                    if sig is not None:
                                        signal.signal(sig, signal.SIG_DFL)

                            if start_new_session:
                                os.setsid()

                            if env is None:
                                os.execvp(executable, args)
                            else:
                                if PY3:
                                    # Python 3.6 started testing for
                                    # bytes values in the env; it also
                                    # started encoding strs using
                                    # fsencode and using a lower-level
                                    # API that takes a list of keys
                                    # and values. We don't have access
                                    # to that API, so we go the reverse direction.
                                    env = {os.fsdecode(k) if isinstance(k, bytes) else k:
                                           os.fsdecode(v) if isinstance(v, bytes) else v
                                           for k, v in env.items()}
                                os.execvpe(executable, args, env)

                        except:
                            exc_type, exc_value, tb = sys.exc_info()
                            # Save the traceback and attach it to the exception object
                            exc_lines = traceback.format_exception(exc_type,
                                                                   exc_value,
                                                                   tb)
                            exc_value.child_traceback = ''.join(exc_lines)
                            os.write(errpipe_write, pickle.dumps(exc_value))

                        finally:
                            # Make sure that the process exits no matter what.
                            # The return code does not matter much as it won't be
                            # reported to the application
                            os._exit(1)

                    # Parent
                    self._child_created = True
                    if gc_was_enabled:
                        gc.enable()
                finally:
                    # be sure the FD is closed no matter what
                    os.close(errpipe_write)

                # self._devnull is not always defined.
                devnull_fd = getattr(self, '_devnull', None)
                if p2cread is not None and p2cwrite is not None and p2cread != devnull_fd:
                    os.close(p2cread)
                if c2pwrite is not None and c2pread is not None and c2pwrite != devnull_fd:
                    os.close(c2pwrite)
                if errwrite is not None and errread is not None and errwrite != devnull_fd:
                    os.close(errwrite)
                if devnull_fd is not None:
                    os.close(devnull_fd)
                # Prevent a double close of these fds from __init__ on error.
                self._closed_child_pipe_fds = True

                # Wait for exec to fail or succeed; possibly raising exception
                errpipe_read = FileObject(errpipe_read, 'rb')
                data = errpipe_read.read()
            finally:
                if hasattr(errpipe_read, 'close'):
                    errpipe_read.close()
                else:
                    os.close(errpipe_read)

            if data != b"":
                self.wait()
                child_exception = pickle.loads(data)
                for fd in (p2cwrite, c2pread, errread):
                    if fd is not None:
                        os.close(fd)
                raise child_exception

        def _handle_exitstatus(self, sts):
            if os.WIFSIGNALED(sts):
                self.returncode = -os.WTERMSIG(sts)
            elif os.WIFEXITED(sts):
                self.returncode = os.WEXITSTATUS(sts)
            else:
                # Should never happen
                raise RuntimeError("Unknown child exit status!")

        def _internal_poll(self):
            """Check if child process has terminated.  Returns returncode
            attribute.
            """
            if self.returncode is None:
                if get_hub() is not getcurrent():
                    sig_pending = getattr(self._loop, 'sig_pending', True)
                    if sig_pending:
                        sleep(0.00001)
            return self.returncode

        def wait(self, timeout=None, _raise_exc=PY3):
            """
            Wait for child process to terminate.  Returns :attr:`returncode`
            attribute.

            :keyword timeout: The floating point number of seconds to
                wait. Under Python 2, this is a gevent extension, and
                we simply return if it expires. Under Python 3, if
                this time elapses without finishing the process,
                :exc:`TimeoutExpired` is raised.
            """
            return self._gevent_result_wait(timeout, _raise_exc)

        def send_signal(self, sig):
            """Send a signal to the process
            """
            # Skip signalling a process that we know has already died.
            if self.returncode is None:
                os.kill(self.pid, sig)

        def terminate(self):
            """Terminate the process with SIGTERM
            """
            self.send_signal(signal.SIGTERM)

        def kill(self):
            """Kill the process with SIGKILL
            """
            self.send_signal(signal.SIGKILL)


def write_and_close(fobj, data):
    try:
        if data:
            fobj.write(data)
            if hasattr(fobj, 'flush'):
                # 3.6 started expecting flush to be called.
                fobj.flush()
    except (OSError, IOError) as ex:
        if ex.errno != errno.EPIPE and ex.errno != errno.EINVAL:
            raise
    finally:
        try:
            fobj.close()
        except EnvironmentError:
            pass

def _with_stdout_stderr(exc, stderr):
    # Prior to Python 3.5, most exceptions didn't have stdout
    # and stderr attributes and can't take the stderr attribute in their
    # constructor
    exc.stdout = exc.output
    exc.stderr = stderr
    return exc

class CompletedProcess(object):
    """
    A process that has finished running.

    This is returned by run().

    Attributes:
      - args: The list or str args passed to run().
      - returncode: The exit code of the process, negative for signals.
      - stdout: The standard output (None if not captured).
      - stderr: The standard error (None if not captured).

    .. versionadded:: 1.2a1
       This first appeared in Python 3.5 and is available to all
       Python versions in gevent.
    """
    def __init__(self, args, returncode, stdout=None, stderr=None):
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        args = ['args={!r}'.format(self.args),
                'returncode={!r}'.format(self.returncode)]
        if self.stdout is not None:
            args.append('stdout={!r}'.format(self.stdout))
        if self.stderr is not None:
            args.append('stderr={!r}'.format(self.stderr))
        return "{}({})".format(type(self).__name__, ', '.join(args))

    def check_returncode(self):
        """Raise CalledProcessError if the exit code is non-zero."""
        if self.returncode:
            raise _with_stdout_stderr(CalledProcessError(self.returncode, self.args, self.stdout), self.stderr)


def run(*popenargs, **kwargs):
    """
    run(args, *, stdin=None, input=None, stdout=None, stderr=None, shell=False, timeout=None, check=False) -> CompletedProcess

    Run command with arguments and return a CompletedProcess instance.

    The returned instance will have attributes args, returncode, stdout and
    stderr. By default, stdout and stderr are not captured, and those attributes
    will be None. Pass stdout=PIPE and/or stderr=PIPE in order to capture them.
    If check is True and the exit code was non-zero, it raises a
    CalledProcessError. The CalledProcessError object will have the return code
    in the returncode attribute, and output & stderr attributes if those streams
    were captured.

    If timeout is given, and the process takes too long, a TimeoutExpired
    exception will be raised.

    There is an optional argument "input", allowing you to
    pass a string to the subprocess's stdin.  If you use this argument
    you may not also use the Popen constructor's "stdin" argument, as
    it will be used internally.
    The other arguments are the same as for the Popen constructor.
    If universal_newlines=True is passed, the "input" argument must be a
    string and stdout/stderr in the returned object will be strings rather than
    bytes.

    .. versionadded:: 1.2a1
       This function first appeared in Python 3.5. It is available on all Python
       versions gevent supports.
    """
    input = kwargs.pop('input', None)
    timeout = kwargs.pop('timeout', None)
    check = kwargs.pop('check', False)

    if input is not None:
        if 'stdin' in kwargs:
            raise ValueError('stdin and input arguments may not both be used.')
        kwargs['stdin'] = PIPE

    with Popen(*popenargs, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            raise _with_stdout_stderr(TimeoutExpired(process.args, timeout, output=stdout), stderr)
        except:
            process.kill()
            process.wait()
            raise
        retcode = process.poll()
        if check and retcode:
            raise _with_stdout_stderr(CalledProcessError(retcode, process.args, stdout), stderr)

    return CompletedProcess(process.args, retcode, stdout, stderr)
