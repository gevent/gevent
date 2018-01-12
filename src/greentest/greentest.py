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
# pylint:disable=broad-except,unused-argument,no-member,too-many-branches,unused-variable
# pylint:disable=attribute-defined-outside-init,abstract-method
import sys
import types
import unittest
from unittest import TestCase as BaseTestCase
from unittest.util import safe_repr
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
import _six as six


PYPY = hasattr(sys, 'pypy_version_info')
VERBOSE = sys.argv.count('-v') > 1
WIN = sys.platform.startswith("win")
LINUX = sys.platform.startswith('linux')

# XXX: Formalize this better
LIBUV = os.getenv('GEVENT_CORE_CFFI_ONLY') == 'libuv' or (PYPY and WIN) or hasattr(gevent.core, 'libuv')
CFFI_BACKEND = bool(os.getenv('GEVENT_CORE_CFFI_ONLY')) or PYPY

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
if WIN:
    PLATFORM_SPECIFIC_SUFFIXES.append('posix')

PY2 = None
PY3 = None
PY34 = None
PY36 = None
PY37 = None

NON_APPLICABLE_SUFFIXES = []
if sys.version_info[0] == 3:
    # Python 3
    NON_APPLICABLE_SUFFIXES.extend(('2', '279'))
    PY2 = False
    PY3 = True
    if sys.version_info[1] >= 4:
        PY34 = True
    if sys.version_info[1] >= 6:
        PY36 = True
    if sys.version_info[1] >= 7:
        PY37 = True

elif sys.version_info[0] == 2:
    # Any python 2
    PY3 = False
    PY2 = True
    NON_APPLICABLE_SUFFIXES.append('3')
    if (sys.version_info[1] < 7
            or (sys.version_info[1] == 7 and sys.version_info[2] < 9)):
        # Python 2, < 2.7.9
        NON_APPLICABLE_SUFFIXES.append('279')

PYPY3 = PYPY and PY3

if WIN:
    NON_APPLICABLE_SUFFIXES.append("posix")
    # This is intimately tied to FileObjectPosix
    NON_APPLICABLE_SUFFIXES.append("fileobject2")
    SHARED_OBJECT_EXTENSION = ".pyd"
else:
    SHARED_OBJECT_EXTENSION = ".so"


RUNNING_ON_TRAVIS = os.environ.get('TRAVIS')
RUNNING_ON_APPVEYOR = os.environ.get('APPVEYOR')
RUNNING_ON_CI = RUNNING_ON_TRAVIS or RUNNING_ON_APPVEYOR

def _do_not_skip(reason):
    def dec(f):
        return f
    return dec

if WIN:
    skipOnWindows = unittest.skip
else:
    skipOnWindows = _do_not_skip

if RUNNING_ON_APPVEYOR:
    # See comments scattered around about timeouts and the timer
    # resolution available on appveyor (lots of jitter). this
    # seems worse with the 62-bit builds.
    # Note that we skip/adjust these tests only on AppVeyor, not
    # win32---we don't think there's gevent related problems but
    # environment related problems. These can be tested and debugged
    # separately on windows in a more stable environment.
    skipOnAppVeyor = unittest.skip

    # We can't exec corecext on appveyor if we haven't run setup.py in
    # 'develop' mode (i.e., we install)
    NON_APPLICABLE_SUFFIXES.append('corecext')
else:
    skipOnAppVeyor = _do_not_skip

if PYPY3 and RUNNING_ON_CI:
    # Same as above, for PyPy3.3-5.5-alpha and 3.5-5.7.1-beta and 3.5-5.8
    skipOnPyPy3OnCI = unittest.skip
else:
    skipOnPyPy3OnCI = _do_not_skip

if PYPY:
    skipOnPyPy = unittest.skip
else:
    skipOnPyPy = _do_not_skip

if PYPY3:
    skipOnPyPy3 = unittest.skip
else:
    skipOnPyPy3 = _do_not_skip

skipIf = unittest.skipIf

EXPECT_POOR_TIMER_RESOLUTION = PYPY3 or RUNNING_ON_APPVEYOR

skipOnLibuv = _do_not_skip
skipOnLibuvOnCI = _do_not_skip
skipOnLibuvOnCIOnPyPy = _do_not_skip

if LIBUV:
    skipOnLibuv = unittest.skip

    if RUNNING_ON_CI:
        skipOnLibuvOnCI = unittest.skip
        if PYPY:
            skipOnLibuvOnCIOnPyPy = unittest.skip

class ExpectedException(Exception):
    """An exception whose traceback should be ignored by the hub"""


# The next exceptions allow us to raise them in a highly
# greppable way so that we can debug them later.

class FlakyTest(unittest.SkipTest):
    """
    A unittest exception that causes the test to be skipped when raised.

    Use this carefully, it is a code smell and indicates an undebugged problem.
    """

class FlakyTestRaceCondition(FlakyTest):
    """
    Use this when the flaky test is definitely caused by a race condition.
    """

class FlakyTestTimeout(FlakyTest):
    """
    Use this when the flaky test is definitely caused by an
    unexpected timeout.
    """

class FlakyTestCrashes(FlakyTest):
    """
    Use this when the test sometimes crashes.
    """

def reraiseFlakyTestRaceCondition():
    six.reraise(*sys.exc_info())

reraiseFlakyTestTimeout = reraiseFlakyTestRaceCondition
reraiseFlakyTestRaceConditionLibuv = reraiseFlakyTestRaceCondition
reraiseFlakyTestTimeoutLibuv = reraiseFlakyTestRaceCondition

if RUNNING_ON_CI:
    # pylint: disable=function-redefined
    def reraiseFlakyTestRaceCondition():
        six.reraise(FlakyTestRaceCondition,
                    FlakyTestRaceCondition('\n'.join(dump_stacks())),
                    sys.exc_info()[2])

    def reraiseFlakyTestTimeout():
        six.reraise(FlakyTestTimeout,
                    FlakyTestTimeout(),
                    sys.exc_info()[2])

    if LIBUV:
        reraiseFlakyTestRaceConditionLibuv = reraiseFlakyTestRaceCondition
        reraiseFlakyTestTimeoutLibuv = reraiseFlakyTestTimeout


def wrap_switch_count_check(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
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
    return wrapper


def wrap_timeout(timeout, method):
    if timeout is None:
        return method

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with gevent.Timeout(timeout, 'test timed out', ref=False):
            return method(self, *args, **kwargs)

    return wrapper

def ignores_leakcheck(func):
    func.ignore_leakcheck = True
    return func

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
    def wrapper(self, *args, **kwargs):
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
                try:
                    method(self, *args, **kwargs)
                finally:
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
                    raise AssertionError("Generated uncollectable garbage %r" % (gc.garbage,))

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

    return wrapper


def wrap_error_fatal(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        # XXX should also be able to do gevent.SYSTEM_ERROR = object
        # which is a global default to all hubs
        SYSTEM_ERROR = gevent.get_hub().SYSTEM_ERROR
        gevent.get_hub().SYSTEM_ERROR = object
        try:
            return method(self, *args, **kwargs)
        finally:
            gevent.get_hub().SYSTEM_ERROR = SYSTEM_ERROR
    return wrapper


def wrap_restore_handle_error(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        old = gevent.get_hub().handle_error
        try:
            return method(self, *args, **kwargs)
        finally:
            gevent.get_hub().handle_error = old
        if self.peek_error()[0] is not None:
            gevent.getcurrent().throw(*self.peek_error()[1:])
    return wrapper


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
    def __new__(cls, classname, bases, classDict):
        # pylint and pep8 fight over what this should be called (mcs or cls).
        # pylint gets it right, but we cant scope disable pep8, so we go with
        # its convention.
        # pylint: disable=bad-mcs-classmethod-argument
        timeout = classDict.get('__timeout__', 'NONE')
        if timeout == 'NONE':
            timeout = getattr(bases[0], '__timeout__', None)
            if RUN_LEAKCHECKS and timeout is not None:
                timeout *= 6
        check_totalrefcount = _get_class_attr(classDict, bases, 'check_totalrefcount', True)
        error_fatal = _get_class_attr(classDict, bases, 'error_fatal', True)
        # Python 3: must copy, we mutate the classDict. Interestingly enough,
        # it doesn't actually error out, but under 3.6 we wind up wrapping
        # and re-wrapping the same items over and over and over.
        for key, value in list(classDict.items()):
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
        return type.__new__(cls, classname, bases, classDict)

# Travis is slow and overloaded; Appveyor used to be faster, but
# as of Dec 2015 it's almost always slower and/or has much worse timer
# resolution
CI_TIMEOUT = 10
if (PY3 and PYPY) or (PYPY and WIN and LIBUV):
    # pypy3 is very slow right now,
    # as is PyPy2 on windows (which only has libuv)
    CI_TIMEOUT = 15
if PYPY and LIBUV:
    # slow and flaky timeouts
    LOCAL_TIMEOUT = CI_TIMEOUT
else:
    LOCAL_TIMEOUT = 1

LARGE_TIMEOUT = max(LOCAL_TIMEOUT, CI_TIMEOUT)

DEFAULT_LOCAL_HOST_ADDR = 'localhost'
DEFAULT_LOCAL_HOST_ADDR6 = DEFAULT_LOCAL_HOST_ADDR
DEFAULT_BIND_ADDR = ''

if RUNNING_ON_TRAVIS:
    # As of November 2017 (probably Sept or Oct), after a
    # Travis upgrade, using "localhost" no longer works,
    # producing 'OSError: [Errno 99] Cannot assign
    # requested address'. This is apparently something to do with
    # docker containers. Sigh.
    DEFAULT_LOCAL_HOST_ADDR = '127.0.0.1'
    DEFAULT_LOCAL_HOST_ADDR6 = '::1'
    # Likewise, binding to '' appears to work, but it cannot be
    # connected to with the same error.
    DEFAULT_BIND_ADDR = '127.0.0.1'

class TestCase(TestCaseMetaClass("NewBase", (BaseTestCase,), {})):
    __timeout__ = LOCAL_TIMEOUT if not RUNNING_ON_CI else CI_TIMEOUT
    switch_expected = 'default'
    error_fatal = True
    close_on_teardown = ()

    def run(self, *args, **kwargs):
        # pylint:disable=arguments-differ
        if self.switch_expected == 'default':
            self.switch_expected = get_switch_expected(self.fullname)
        return BaseTestCase.run(self, *args, **kwargs)

    def setUp(self):
        super(TestCase, self).setUp()
        self.close_on_teardown = []

    def tearDown(self):
        if getattr(self, 'skipTearDown', False):
            return
        if hasattr(self, 'cleanup'):
            self.cleanup()
        self._error = self._none
        self._tearDownCloseOnTearDown()
        self.close_on_teardown = []
        super(TestCase, self).tearDown()

    def _tearDownCloseOnTearDown(self):
        # XXX: Should probably reverse this
        for x in self.close_on_teardown:
            close = getattr(x, 'close', x)
            try:
                close()
            except Exception:
                pass

    @classmethod
    def setUpClass(cls):
        import warnings
        cls._warning_cm = warnings.catch_warnings()
        cls._warning_cm.__enter__()
        if not sys.warnoptions:
            warnings.simplefilter('default')
        super(TestCase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls._warning_cm.__exit__(None, None, None)
        super(TestCase, cls).tearDownClass()

    def _close_on_teardown(self, resource):
        """
        *resource* either has a ``close`` method, or is a
        callable.
        """
        self.close_on_teardown.append(resource)
        return resource

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
    # (context, kind, value)
    _error = _none

    def expect_one_error(self):
        assert self._error == self._none, self._error
        self._old_handle_error = gevent.get_hub().handle_error
        gevent.get_hub().handle_error = self._store_error

    def _store_error(self, where, t, value, tb):
        del tb
        if self._error != self._none:
            gevent.get_hub().parent.throw(t, value)
        else:
            self._error = (where, t, value)

    def peek_error(self):
        return self._error

    def get_error(self):
        try:
            return self._error
        finally:
            self._error = self._none

    def assert_error(self, kind=None, value=None, error=None, where_type=None):
        if error is None:
            error = self.get_error()
        econtext, ekind, evalue = error
        if kind is not None:
            self.assertIsInstance(kind, type)
            try:
                assert issubclass(ekind, kind), error
            except TypeError as e:
                # Seen on PyPy on Windows
                print("TYPE ERROR", e, ekind, kind, type(kind))
                raise
        if value is not None:
            if isinstance(value, str):
                self.assertEqual(str(evalue), value)
            else:
                self.assertIs(evalue, value)
        if where_type is not None:
            self.assertIsInstance(econtext, where_type)
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

    if not hasattr(BaseTestCase, 'assertIsNot'):
        # Methods added in 3.1, backport for 2.7
        def assertIs(self, expr1, expr2, msg=None):
            """Just like self.assertTrue(a is b), but with a nicer default message."""
            if expr1 is not expr2:
                standardMsg = '%s is not %s' % (safe_repr(expr1),
                                                safe_repr(expr2))
                self.fail(self._formatMessage(msg, standardMsg))

        def assertIsNot(self, expr1, expr2, msg=None):
            """Just like self.assertTrue(a is not b), but with a nicer default message."""
            if expr1 is expr2:
                standardMsg = 'unexpectedly identical: %s' % (safe_repr(expr1),)
                self.fail(self._formatMessage(msg, standardMsg))

    def assertMonkeyPatchedFuncSignatures(self, mod_name, func_names=(), exclude=()):
        # We use inspect.getargspec because it's the only thing available
        # in Python 2.7, but it is deprecated
        # pylint:disable=deprecated-method
        import inspect
        import warnings
        from gevent.monkey import get_original
        # XXX: Very similar to gevent.monkey.patch_module. Should refactor?
        gevent_module = getattr(__import__('gevent.' + mod_name), mod_name)
        module_name = getattr(gevent_module, '__target__', mod_name)

        funcs_given = True
        if not func_names:
            funcs_given = False
            func_names = getattr(gevent_module, '__implements__')

        for func_name in func_names:
            if func_name in exclude:
                continue
            gevent_func = getattr(gevent_module, func_name)
            if not inspect.isfunction(gevent_func) and not funcs_given:
                continue

            func = get_original(module_name, func_name)

            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    gevent_sig = inspect.getargspec(gevent_func)
                    sig = inspect.getargspec(func)
            except TypeError:
                if funcs_given:
                    raise
                # Can't do this one. If they specifically asked for it,
                # it's an error, otherwise it's not.
                # Python 3 can check a lot more than Python 2 can.
                continue
            self.assertEqual(sig.args, gevent_sig.args, func_name)
            # The next three might not actually matter?
            self.assertEqual(sig.varargs, gevent_sig.varargs, func_name)
            self.assertEqual(sig.keywords, gevent_sig.keywords, func_name)
            self.assertEqual(sig.defaults, gevent_sig.defaults, func_name)

if not hasattr(TestCase, 'assertRaisesRegex'):
    TestCase.assertRaisesRegex = TestCase.assertRaisesRegexp

main = unittest.main
_original_Hub = gevent.hub.Hub


class CountingHub(_original_Hub):

    EXPECTED_TEST_ERROR = (ExpectedException,)

    switch_count = 0

    def switch(self, *args):
        # pylint:disable=arguments-differ
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
        # and subject to jitter.
        _default_delay_max_adj = 1.5

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
        # and subject to jitter
        _default_delay_max_adj = 1.5

    @ignores_leakcheck # waiting checks can be very sensitive to timing
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
        elif include_so and fn.endswith(SHARED_OBJECT_EXTENSION):
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


import re
# Linux/OS X/BSD platforms can implement this by calling out to lsof


if WIN:
    def _run_lsof():
        raise unittest.SkipTest("lsof not expected on Windows")
else:
    def _run_lsof():
        import tempfile
        pid = os.getpid()
        fd, tmpname = tempfile.mkstemp('get_open_files')
        os.close(fd)
        lsof_command = 'lsof -p %s > %s' % (pid, tmpname)
        if os.system(lsof_command):
            # XXX: This prints to the console an annoying message: 'lsof is not recognized'
            raise unittest.SkipTest("lsof failed")
        with open(tmpname) as fobj:
            data = fobj.read().strip()
        os.remove(tmpname)
        return data

def default_get_open_files(pipes=False):
    data = _run_lsof()
    results = {}
    for line in data.split('\n'):
        line = line.strip()
        if not line or line.startswith("COMMAND"):
            # Skip header and blank lines
            continue
        split = re.split(r'\s+', line)
        command, pid, user, fd = split[:4]
        # Pipes (on OS X, at least) get an fd like "3" while normal files get an fd like "1u"
        if fd[:-1].isdigit() or fd.isdigit():
            if not pipes and fd[-1].isdigit():
                continue
            fd = int(fd[:-1]) if not fd[-1].isdigit() else int(fd)
            if fd in results:
                params = (fd, line, split, results.get(fd), data)
                raise AssertionError('error when parsing lsof output: duplicate fd=%r\nline=%r\nsplit=%r\nprevious=%r\ndata:\n%s' % params)
            results[fd] = line
    if not results:
        raise AssertionError('failed to parse lsof:\n%s' % (data, ))
    results['data'] = data
    return results

def default_get_number_open_files():
    if os.path.exists('/proc/'):
        # Linux only
        fd_directory = '/proc/%d/fd' % os.getpid()
        return len(os.listdir(fd_directory))
    else:
        try:
            return len(get_open_files(pipes=True)) - 1
        except (OSError, AssertionError, unittest.SkipTest):
            return 0

lsof_get_open_files = default_get_open_files

try:
    # psutil import subprocess which on Python 3 imports selectors.
    # This can expose issues with monkey-patching.
    import psutil
except ImportError:
    get_open_files = default_get_open_files
    get_number_open_files = default_get_number_open_files
else:
    # If psutil is available (it is cross-platform) use that.
    # It is *much* faster than shelling out to lsof each time
    # (Running 14 tests takes 3.964s with lsof and 0.046 with psutil)
    # However, it still doesn't completely solve the issue on Windows: fds are reported
    # as -1 there, so we can't fully check those.

    def get_open_files():
        """
        Return a list of popenfile and pconn objects.

        Note that other than `fd`, they have different attributes.

        .. important:: If you want to find open sockets, on Windows
           and linux, it is important that the socket at least be listening
           (socket.listen(1)). Unlike the lsof implementation, this will only
           return sockets in a state like that.
        """
        results = dict()
        process = psutil.Process()
        results['data'] = process.open_files() + process.connections('all')
        for x in results['data']:
            results[x.fd] = x
        results['data'] += ['From psutil', process]
        return results

    def get_number_open_files():
        process = psutil.Process()
        try:
            return process.num_fds()
        except AttributeError:
            # num_fds is unix only. Is num_handles close enough on Windows?
            return 0


if PYPY:

    def getrefcount(*args):
        pass

else:

    def getrefcount(*args):
        return sys.getrefcount(*args)

def dump_stacks():
    """
    Request information about the running threads of the current process.

    :return: A sequence of text lines detailing the stacks of running
            threads and greenlets. (One greenlet will duplicate one thread,
            the current thread and greenlet.)
    """
    dump = []

    # threads
    import threading  # Late import this stuff because it may get monkey-patched
    import traceback
    from greenlet import greenlet

    threads = {th.ident: th.name for th in threading.enumerate()}

    for thread, frame in sys._current_frames().items():
        dump.append('Thread 0x%x (%s)\n' % (thread, threads.get(thread)))
        dump.append(''.join(traceback.format_stack(frame)))
        dump.append('\n')

    # greenlets

    # if greenlet is present, let's dump each greenlet stack
    # Use the gc module to inspect all objects to find the greenlets
    # since there isn't a global registry
    for ob in gc.get_objects():
        if not isinstance(ob, greenlet):
            continue
        if not ob:
            continue  # not running anymore or not started
        dump.append('Greenlet %s\n' % ob)
        dump.append(''.join(traceback.format_stack(ob.gr_frame)))
        dump.append('\n')

    return dump
