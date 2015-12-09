# Copyright (c) 2008-2009 AG Projects
# Author: Denis Bilenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# package is named greentest, not test, so it won't be confused with test in stdlib
import sys
import types
import unittest
from unittest import TestCase as BaseTestCase
import time
import os
from os.path import basename, splitext
import gevent
import gevent.core
from patched_tests_setup import get_switch_expected
from gevent.hub import _get_hub
from functools import wraps
import contextlib
import gc
import six

try:
    from unittest.util import safe_repr
except ImportError:
    # Py 2.6
    _MAX_LENGTH = 80

    def safe_repr(obj, short=False):
        try:
            result = repr(obj)
        except Exception:
            result = object.__repr__(obj)
        if not short or len(result) < _MAX_LENGTH:
            return result
        return result[:_MAX_LENGTH] + ' [truncated]...'


PYPY = hasattr(sys, 'pypy_version_info')
VERBOSE = sys.argv.count('-v') > 1

if '--debug-greentest' in sys.argv:
    sys.argv.remove('--debug-greentest')
    DEBUG = True
else:
    DEBUG = False

RUN_LEAKCHECKS = os.getenv('GEVENTTEST_LEAKCHECK')
OPTIONAL_MODULES = ['resolver_ares']

# Generally, ignore the portions that are only implemented
# on particular platforms; they generally contain partial
# implementations completed in different modules.
PLATFORM_SPECIFIC_SUFFIXES = ['2', '279', '3']
if sys.platform.startswith('win'):
    PLATFORM_SPECIFIC_SUFFIXES.append('posix')

NON_APPLICABLE_SUFFIXES = []
if sys.version_info[0] == 3:
    # Python 3
    NON_APPLICABLE_SUFFIXES.extend(('2', '279'))
    PY2 = False
    PY3 = True
if sys.version_info[0] == 2:
    # Any python 2
    PY3 = False
    PY2 = True
    NON_APPLICABLE_SUFFIXES.append('3')
    if (sys.version_info[1] < 7
        or (sys.version_info[1] == 7 and sys.version_info[2] < 9)):
        # Python 2, < 2.7.9
        NON_APPLICABLE_SUFFIXES.append('279')
if sys.platform.startswith('win'):
    NON_APPLICABLE_SUFFIXES.append("posix")
    # This is intimately tied to FileObjectPosix
    NON_APPLICABLE_SUFFIXES.append("fileobject2")


RUNNING_ON_TRAVIS = os.environ.get('TRAVIS')
RUNNING_ON_APPVEYOR = os.environ.get('APPVEYOR')
RUNNING_ON_CI = RUNNING_ON_TRAVIS or RUNNING_ON_APPVEYOR

if RUNNING_ON_APPVEYOR:
    # See comments scattered around about timeouts and the timer
    # resolution available on appveyor (lots of jitter). this
    # seems worse with the 62-bit builds.
    # Note that we skip/adjust these tests only on AppVeyor, not
    # win32---we don't think there's gevent related problems but
    # environment related problems. These can be tested and debugged
    # separately on windows in a more stable environment.
    skipOnAppVeyor = unittest.skip
else:
    def skipOnAppVeyor(reason):
        def dec(f):
            return f
        return dec


class ExpectedException(Exception):
    """An exception whose traceback should be ignored"""


def wrap_switch_count_check(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        initial_switch_count = getattr(_get_hub(), 'switch_count', None)
        self.switch_expected = getattr(self, 'switch_expected', True)
        if initial_switch_count is not None:
            fullname = getattr(self, 'fullname', None)
            if self.switch_expected == 'default' and fullname:
                self.switch_expected = get_switch_expected(fullname)
        result = method(self, *args, **kwargs)
        if initial_switch_count is not None and self.switch_expected is not None:
            switch_count = _get_hub().switch_count - initial_switch_count
            if self.switch_expected is True:
                assert switch_count >= 0
                if not switch_count:
                    raise AssertionError('%s did not switch' % fullname)
            elif self.switch_expected is False:
                if switch_count:
                    raise AssertionError('%s switched but not expected to' % fullname)
            else:
                raise AssertionError('Invalid value for switch_expected: %r' % (self.switch_expected, ))
        return result
    return wrapped


def wrap_timeout(timeout, method):
    if timeout is None:
        return method

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with gevent.Timeout(timeout, 'test timed out', ref=False):
            return method(self, *args, **kwargs)

    return wrapped


def wrap_refcount(method):
    if not RUN_LEAKCHECKS:
        return method

    if getattr(method, 'ignore_leakcheck', False):
        return method

    # Some builtin things that we ignore
    IGNORED_TYPES = (tuple, dict, types.FrameType, types.TracebackType)

    def type_hist():
        import collections
        d = collections.defaultdict(int)
        for x in gc.get_objects():
            k = type(x)
            if k in IGNORED_TYPES:
                continue
            if k == gevent.core.callback and x.callback is None and x.args is None:
                # these represent callbacks that have been stopped, but
                # the event loop hasn't cycled around to run them. The only
                # known cause of this is killing greenlets before they get a chance
                # to run for the first time.
                continue
            d[k] += 1
        return d

    def report_diff(a, b):
        diff_lines = []
        for k, v in sorted(a.items(), key=lambda i: i[0].__name__):
            if b[k] != v:
                diff_lines.append("%s: %s != %s" % (k, v, b[k]))

        if not diff_lines:
            return None
        diff = '\n'.join(diff_lines)
        return diff

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        gc.collect()
        gc.collect()
        gc.collect()
        deltas = []
        d = None
        gc.disable()
        try:
            while True:

                # Grab current snapshot
                hist_before = type_hist()
                d = sum(hist_before.values())

                self.setUp()
                method(self, *args, **kwargs)
                self.tearDown()

                # Grab post snapshot
                if 'urlparse' in sys.modules:
                    sys.modules['urlparse'].clear_cache()
                if 'urllib.parse' in sys.modules:
                    sys.modules['urllib.parse'].clear_cache()
                hist_after = type_hist()
                d = sum(hist_after.values()) - d
                deltas.append(d)

                # Reset and check for cycles
                gc.collect()
                if gc.garbage:
                    raise AssertionError("Generated uncollectable garbage")

                # the following configurations are classified as "no leak"
                # [0, 0]
                # [x, 0, 0]
                # [... a, b, c, d]  where a+b+c+d = 0
                #
                # the following configurations are classified as "leak"
                # [... z, z, z]  where z > 0
                if deltas[-2:] == [0, 0] and len(deltas) in (2, 3):
                    break
                elif deltas[-3:] == [0, 0, 0]:
                    break
                elif len(deltas) >= 4 and sum(deltas[-4:]) == 0:
                    break
                elif len(deltas) >= 3 and deltas[-1] > 0 and deltas[-1] == deltas[-2] and deltas[-2] == deltas[-3]:
                    diff = report_diff(hist_before, hist_after)
                    raise AssertionError('refcount increased by %r\n%s' % (deltas, diff))
                # OK, we don't know for sure yet. Let's search for more
                if sum(deltas[-3:]) <= 0 or sum(deltas[-4:]) <= 0 or deltas[-4:].count(0) >= 2:
                    # this is suspicious, so give a few more runs
                    limit = 11
                else:
                    limit = 7
                if len(deltas) >= limit:
                    raise AssertionError('refcount increased by %r\n%s' % (deltas, report_diff(hist_before, hist_after)))
        finally:
            gc.enable()
        self.skipTearDown = True

    return wrapped


def wrap_error_fatal(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        # XXX should also be able to do gevent.SYSTEM_ERROR = object
        # which is a global default to all hubs
        SYSTEM_ERROR = gevent.get_hub().SYSTEM_ERROR
        gevent.get_hub().SYSTEM_ERROR = object
        try:
            return method(self, *args, **kwargs)
        finally:
            gevent.get_hub().SYSTEM_ERROR = SYSTEM_ERROR
    return wrapped


def wrap_restore_handle_error(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        old = gevent.get_hub().handle_error
        try:
            return method(self, *args, **kwargs)
        finally:
            gevent.get_hub().handle_error = old
        if self.peek_error()[0] is not None:
            gevent.getcurrent().throw(*self.peek_error()[1:])
    return wrapped


def _get_class_attr(classDict, bases, attr, default=AttributeError):
    NONE = object()
    value = classDict.get(attr, NONE)
    if value is not NONE:
        return value
    for base in bases:
        value = getattr(bases[0], attr, NONE)
        if value is not NONE:
            return value
    if default is AttributeError:
        raise AttributeError('Attribute %r not found\n%s\n%s\n' % (attr, classDict, bases))
    return default


class TestCaseMetaClass(type):
    # wrap each test method with
    # a) timeout check
    # b) fatal error check
    # c) restore the hub's error handler (see expect_one_error)
    # d) totalrefcount check
    def __new__(meta, classname, bases, classDict):
        timeout = classDict.get('__timeout__', 'NONE')
        if timeout == 'NONE':
            timeout = getattr(bases[0], '__timeout__', None)
            if RUN_LEAKCHECKS and timeout is not None:
                timeout *= 6
        check_totalrefcount = _get_class_attr(classDict, bases, 'check_totalrefcount', True)
        error_fatal = _get_class_attr(classDict, bases, 'error_fatal', True)
        for key, value in classDict.items():
            if key.startswith('test') and callable(value):
                classDict.pop(key)
                #value = wrap_switch_count_check(value)
                value = wrap_timeout(timeout, value)
                my_error_fatal = getattr(value, 'error_fatal', None)
                if my_error_fatal is None:
                    my_error_fatal = error_fatal
                if my_error_fatal:
                    value = wrap_error_fatal(value)
                value = wrap_restore_handle_error(value)
                if check_totalrefcount:
                    value = wrap_refcount(value)
                classDict[key] = value
        return type.__new__(meta, classname, bases, classDict)


class TestCase(TestCaseMetaClass("NewBase", (BaseTestCase,), {})):
    # Travis is slow and overloaded; Appveyor used to be faster, but
    # as of Dec 2015 it's almost always slower and/or has much worse timer
    # resolution
    __timeout__ = 1 if not RUNNING_ON_CI else 5
    switch_expected = 'default'
    error_fatal = True

    def run(self, *args, **kwargs):
        if self.switch_expected == 'default':
            self.switch_expected = get_switch_expected(self.fullname)
        return BaseTestCase.run(self, *args, **kwargs)

    def tearDown(self):
        if getattr(self, 'skipTearDown', False):
            return
        if hasattr(self, 'cleanup'):
            self.cleanup()
        self._error = self._none

    @property
    def testname(self):
        return getattr(self, '_testMethodName', '') or getattr(self, '_TestCase__testMethodName')

    @property
    def testcasename(self):
        return self.__class__.__name__ + '.' + self.testname

    @property
    def modulename(self):
        return os.path.basename(sys.modules[self.__class__.__module__].__file__).rsplit('.', 1)[0]

    @property
    def fullname(self):
        return splitext(basename(self.modulename))[0] + '.' + self.testcasename

    _none = (None, None, None)
    _error = _none

    def expect_one_error(self):
        assert self._error == self._none, self._error
        self._old_handle_error = gevent.get_hub().handle_error
        gevent.get_hub().handle_error = self._store_error

    def _store_error(self, where, type, value, tb):
        del tb
        if self._error != self._none:
            gevent.get_hub().parent.throw(type, value)
        else:
            self._error = (where, type, value)

    def peek_error(self):
        return self._error

    def get_error(self):
        try:
            return self._error
        finally:
            self._error = self._none

    def assert_error(self, type=None, value=None, error=None):
        if error is None:
            error = self.get_error()
        if type is not None:
            assert issubclass(error[1], type), error
        if value is not None:
            if isinstance(value, str):
                assert str(error[2]) == value, error
            else:
                assert error[2] is value, error
        return error

    if RUNNING_ON_APPVEYOR:
        # appveyor timeouts are unreliable; seems to be very slow wakeups
        def assertTimeoutAlmostEqual(self, *args, **kwargs):
            return

        def assertTimeWithinRange(self, delay, min_time, max_time):
            return
    else:
        def assertTimeoutAlmostEqual(self, *args, **kwargs):
            self.assertAlmostEqual(*args, **kwargs)

        def assertTimeWithinRange(self, delay, min_time, max_time):
            self.assertLessEqual(delay, max_time)
            self.assertGreaterEqual(delay, min_time)

    if not hasattr(BaseTestCase, 'assertGreater'):
        # Compatibility with 2.6, backported from 2.7
        longMessage = False

        def _formatMessage(self, msg, standardMsg):
            """Honour the longMessage attribute when generating failure messages.
            If longMessage is False this means:
            * Use only an explicit message if it is provided
            * Otherwise use the standard message for the assert

            If longMessage is True:
            * Use the standard message
            * If an explicit message is provided, plus ' : ' and the explicit message
            """
            if not self.longMessage:
                return msg or standardMsg
            if msg is None:
                return standardMsg
            try:
                # don't switch to '{}' formatting in Python 2.X
                # it changes the way unicode input is handled
                return '%s : %s' % (standardMsg, msg)
            except UnicodeDecodeError:
                return '%s : %s' % (safe_repr(standardMsg), safe_repr(msg))

        def assertLess(self, a, b, msg=None):
            """Just like self.assertTrue(a < b), but with a nicer default message."""
            if not a < b:
                standardMsg = '%s not less than %s' % (safe_repr(a), safe_repr(b))
                self.fail(self._formatMessage(msg, standardMsg))

        def assertLessEqual(self, a, b, msg=None):
            """Just like self.assertTrue(a <= b), but with a nicer default message."""
            if not a <= b:
                standardMsg = '%s not less than or equal to %s' % (safe_repr(a), safe_repr(b))
                self.fail(self._formatMessage(msg, standardMsg))

        def assertGreater(self, a, b, msg=None):
            """Just like self.assertTrue(a > b), but with a nicer default message."""
            if not a > b:
                standardMsg = '%s not greater than %s' % (safe_repr(a), safe_repr(b))
                self.fail(self._formatMessage(msg, standardMsg))

        def assertGreaterEqual(self, a, b, msg=None):
            """Just like self.assertTrue(a >= b), but with a nicer default message."""
            if not a >= b:
                standardMsg = '%s not greater than or equal to %s' % (safe_repr(a), safe_repr(b))
                self.fail(self._formatMessage(msg, standardMsg))


main = unittest.main
_original_Hub = gevent.hub.Hub


class CountingHub(_original_Hub):

    EXPECTED_TEST_ERROR = (ExpectedException,)

    switch_count = 0

    def switch(self, *args):
        self.switch_count += 1
        return _original_Hub.switch(self, *args)

    def handle_error(self, context, type, value, tb):
        if issubclass(type, self.EXPECTED_TEST_ERROR):
            # Don't print these to cut down on the noise in the test logs
            return
        return _original_Hub.handle_error(self, context, type, value, tb)

gevent.hub.Hub = CountingHub


class _DelayWaitMixin(object):

    _default_wait_timeout = 0.01
    _default_delay_min_adj = 0.001
    if not RUNNING_ON_APPVEYOR:
        _default_delay_max_adj = 0.11
    else:
        # Timing resolution is extremely poor on Appveyor
        _default_delay_max_adj = 0.9

    def wait(self, timeout):
        raise NotImplementedError('override me in subclass')

    def _check_delay_bounds(self, timeout, delay,
                            delay_min_adj=None,
                            delay_max_adj=None):
        delay_min_adj = self._default_delay_min_adj if not delay_min_adj else delay_min_adj
        delay_max_adj = self._default_delay_max_adj if not delay_max_adj else delay_max_adj
        self.assertGreaterEqual(delay, timeout - delay_min_adj)
        self.assertLess(delay, timeout + delay_max_adj)

    def _wait_and_check(self, timeout=None):
        if timeout is None:
            timeout = self._default_wait_timeout

        # gevent.timer instances have a 'seconds' attribute,
        # otherwise it's the raw number
        seconds = getattr(timeout, 'seconds', timeout)

        start = time.time()
        try:
            result = self.wait(timeout)
        finally:
            self._check_delay_bounds(seconds, time.time() - start,
                                     self._default_delay_min_adj,
                                     self._default_delay_max_adj)
        return result

    def test_outer_timeout_is_not_lost(self):
        timeout = gevent.Timeout.start_new(0.001, ref=False)
        try:
            try:
                result = self.wait(timeout=1)
            except gevent.Timeout as ex:
                assert ex is timeout, (ex, timeout)
            else:
                raise AssertionError('must raise Timeout (returned %r)' % (result, ))
        finally:
            timeout.cancel()


class GenericWaitTestCase(_DelayWaitMixin, TestCase):

    _default_wait_timeout = 0.2
    _default_delay_min_adj = 0.1
    if not RUNNING_ON_APPVEYOR:
        _default_delay_max_adj = 0.11
    else:
        # Timing resolution is very poor on Appveyor
        _default_delay_max_adj = 0.9

    def test_returns_none_after_timeout(self):
        result = self._wait_and_check()
        # join and wait simply return after timeout expires
        assert result is None, repr(result)


class GenericGetTestCase(_DelayWaitMixin, TestCase):

    Timeout = gevent.Timeout

    def cleanup(self):
        pass

    def test_raises_timeout_number(self):
        self.assertRaises(self.Timeout, self._wait_and_check, timeout=0.01)
        # get raises Timeout after timeout expired
        self.cleanup()

    def test_raises_timeout_Timeout(self):
        timeout = gevent.Timeout(self._default_wait_timeout)
        try:
            self._wait_and_check(timeout=timeout)
        except gevent.Timeout as ex:
            assert ex is timeout, (ex, timeout)
        self.cleanup()

    def test_raises_timeout_Timeout_exc_customized(self):
        error = RuntimeError('expected error')
        timeout = gevent.Timeout(self._default_wait_timeout, exception=error)
        try:
            self._wait_and_check(timeout=timeout)
        except RuntimeError as ex:
            assert ex is error, (ex, error)
        self.cleanup()


def walk_modules(basedir=None, modpath=None, include_so=False, recursive=False):
    if PYPY:
        include_so = False
    if basedir is None:
        basedir = os.path.dirname(gevent.__file__)
        if modpath is None:
            modpath = 'gevent.'
    else:
        if modpath is None:
            modpath = ''
    for fn in sorted(os.listdir(basedir)):
        path = os.path.join(basedir, fn)
        if os.path.isdir(path):
            if not recursive:
                continue
            pkg_init = os.path.join(path, '__init__.py')
            if os.path.exists(pkg_init):
                yield pkg_init, modpath + fn
                for p, m in walk_modules(path, modpath + fn + "."):
                    yield p, m
            continue
        if fn.endswith('.py'):
            x = fn[:-3]
            if x.endswith('_d'):
                x = x[:-2]
            if x in ['__init__', 'core', 'ares', '_util', '_semaphore',
                     'corecffi', '_corecffi', '_corecffi_build']:
                continue
            if x in OPTIONAL_MODULES:
                try:
                    six.exec_("import %s" % x, {})
                except ImportError:
                    continue
            yield path, modpath + x
        elif include_so and fn.endswith('.so'):
            if '.pypy-' in fn:
                continue
            if fn.endswith('_d.so'):
                yield path, modpath + fn[:-5]
            else:
                yield path, modpath + fn[:-3]


def bind_and_listen(sock, address=('', 0), backlog=50, reuse_addr=True):
    from socket import SOL_SOCKET, SO_REUSEADDR, error
    if reuse_addr:
        try:
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, sock.getsockopt(SOL_SOCKET, SO_REUSEADDR) | 1)
        except error:
            pass
    sock.bind(address)
    sock.listen(backlog)


def tcp_listener(address, backlog=50, reuse_addr=True):
    """A shortcut to create a TCP socket, bind it and put it into listening state."""
    from gevent import socket
    sock = socket.socket()
    bind_and_listen(sock)
    return sock


@contextlib.contextmanager
def disabled_gc():
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def get_number_open_files():
    if os.path.exists('/proc/'):
        fd_directory = '/proc/%d/fd' % os.getpid()
        return len(os.listdir(fd_directory))


if PYPY:

    def getrefcount(*args):
        pass

else:

    def getrefcount(*args):
        return sys.getrefcount(*args)
