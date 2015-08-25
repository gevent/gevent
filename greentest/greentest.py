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

PYPY = hasattr(sys, 'pypy_version_info')
VERBOSE = sys.argv.count('-v') > 1

if '--debug-greentest' in sys.argv:
    sys.argv.remove('--debug-greentest')
    DEBUG = True
else:
    DEBUG = False

gettotalrefcount = getattr(sys, 'gettotalrefcount', None)
OPTIONAL_MODULES = ['resolver_ares']


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
    if not os.getenv('GEVENTTEST_LEAKCHECK'):
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
            if gettotalrefcount is not None and timeout is not None:
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
    __timeout__ = 1 if not os.environ.get('TRAVIS') else 2 # Travis is slow and overloaded
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

if gettotalrefcount is None:
    gevent.hub.Hub = CountingHub


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


class GenericWaitTestCase(TestCase):

    def wait(self, timeout):
        raise NotImplementedError('override me in subclass')

    test_outer_timeout_is_not_lost = test_outer_timeout_is_not_lost

    def test_returns_none_after_timeout(self):
        start = time.time()
        result = self.wait(timeout=0.2)
        # join and wait simply return after timeout expires
        delay = time.time() - start
        assert 0.2 - 0.1 <= delay < 0.2 + 0.1, delay
        assert result is None, repr(result)


class GenericGetTestCase(TestCase):

    Timeout = gevent.Timeout

    def wait(self, timeout):
        raise NotImplementedError('override me in subclass')

    def cleanup(self):
        pass

    test_outer_timeout_is_not_lost = test_outer_timeout_is_not_lost

    def test_raises_timeout_number(self):
        start = time.time()
        self.assertRaises(self.Timeout, self.wait, timeout=0.01)
        # get raises Timeout after timeout expired
        delay = time.time() - start
        assert 0.01 - 0.001 <= delay < 0.01 + 0.01 + 0.1, delay
        self.cleanup()

    def test_raises_timeout_Timeout(self):
        start = time.time()
        timeout = gevent.Timeout(0.01)
        try:
            self.wait(timeout=timeout)
        except gevent.Timeout as ex:
            assert ex is timeout, (ex, timeout)
        delay = time.time() - start
        assert 0.01 - 0.001 <= delay < 0.01 + 0.01 + 0.1, delay
        self.cleanup()

    def test_raises_timeout_Timeout_exc_customized(self):
        start = time.time()
        error = RuntimeError('expected error')
        timeout = gevent.Timeout(0.01, exception=error)
        try:
            self.wait(timeout=timeout)
        except RuntimeError as ex:
            assert ex is error, (ex, error)
        delay = time.time() - start
        assert 0.01 - 0.001 <= delay < 0.01 + 0.01 + 0.1, delay
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
            if x in ['__init__', 'core', 'ares', '_util', '_semaphore', 'corecffi']:
                continue
            if x in OPTIONAL_MODULES:
                try:
                    six.exec_("import %s" % x, {})
                except ImportError:
                    continue
            yield path, modpath + x
        elif include_so and fn.endswith('.so'):
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
