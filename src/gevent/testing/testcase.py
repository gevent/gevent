# Copyright (c) 2018 gevent community
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
from __future__ import absolute_import, print_function, division

import sys
from time import time
import os.path
from contextlib import contextmanager
from unittest import TestCase as BaseTestCase
from functools import wraps

import gevent

from . import sysinfo
from . import params
from . import leakcheck
from . import errorhandler
from . import flaky

from .patched_tests_setup import get_switch_expected

class TimeAssertMixin(object):
    @flaky.reraises_flaky_timeout()
    def assertTimeoutAlmostEqual(self, first, second, places=None, msg=None, delta=None):
        try:
            self.assertAlmostEqual(first, second, places=places, msg=msg, delta=delta)
        except AssertionError:
            flaky.reraiseFlakyTestTimeout()


    if sysinfo.EXPECT_POOR_TIMER_RESOLUTION:
        # pylint:disable=unused-argument
        def assertTimeWithinRange(self, time_taken, min_time, max_time):
            return
    else:
        def assertTimeWithinRange(self, time_taken, min_time, max_time):
            self.assertLessEqual(time_taken, max_time)
            self.assertGreaterEqual(time_taken, min_time)

    @contextmanager
    def runs_in_given_time(self, expected, fuzzy=None):
        if fuzzy is None:
            if sysinfo.EXPECT_POOR_TIMER_RESOLUTION or sysinfo.LIBUV:
                # The noted timer jitter issues on appveyor/pypy3
                fuzzy = expected * 5.0
            else:
                fuzzy = expected / 2.0
        start = time()
        yield
        elapsed = time() - start
        try:
            self.assertTrue(
                expected - fuzzy <= elapsed <= expected + fuzzy,
                'Expected: %r; elapsed: %r; fuzzy %r' % (expected, elapsed, fuzzy))
        except AssertionError:
            flaky.reraiseFlakyTestRaceCondition()

    def runs_in_no_time(
            self,
            fuzzy=(0.01 if not sysinfo.EXPECT_POOR_TIMER_RESOLUTION and not sysinfo.LIBUV else 1.0)):
        return self.runs_in_given_time(0.0, fuzzy)


def _wrap_timeout(timeout, method):
    if timeout is None:
        return method

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with gevent.Timeout(timeout, 'test timed out', ref=False):
            return method(self, *args, **kwargs)

    return wrapper

def _get_class_attr(classDict, bases, attr, default=AttributeError):
    NONE = object()
    value = classDict.get(attr, NONE)
    if value is not NONE:
        return value
    for base in bases:
        value = getattr(base, attr, NONE)
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
            if sysinfo.RUN_LEAKCHECKS and timeout is not None:
                timeout *= 6
        check_totalrefcount = _get_class_attr(classDict, bases, 'check_totalrefcount', True)

        error_fatal = _get_class_attr(classDict, bases, 'error_fatal', True)
        uses_handle_error = _get_class_attr(classDict, bases, 'uses_handle_error', True)
        # Python 3: must copy, we mutate the classDict. Interestingly enough,
        # it doesn't actually error out, but under 3.6 we wind up wrapping
        # and re-wrapping the same items over and over and over.
        for key, value in list(classDict.items()):
            if key.startswith('test') and callable(value):
                classDict.pop(key)
                # XXX: When did we stop doing this?
                #value = wrap_switch_count_check(value)
                value = _wrap_timeout(timeout, value)
                error_fatal = getattr(value, 'error_fatal', error_fatal)
                if error_fatal:
                    value = errorhandler.wrap_error_fatal(value)
                if uses_handle_error:
                    value = errorhandler.wrap_restore_handle_error(value)
                if check_totalrefcount and sysinfo.RUN_LEAKCHECKS:
                    value = leakcheck.wrap_refcount(value)
                classDict[key] = value
        return type.__new__(cls, classname, bases, classDict)

def _noop():
    return

class SubscriberCleanupMixin(object):

    def setUp(self):
        super(SubscriberCleanupMixin, self).setUp()
        from gevent import events
        self.__old_subscribers = events.subscribers[:]

    def tearDown(self):
        from gevent import events
        events.subscribers[:] = self.__old_subscribers
        super(SubscriberCleanupMixin, self).tearDown()


class TestCase(TestCaseMetaClass("NewBase",
                                 (SubscriberCleanupMixin, TimeAssertMixin, BaseTestCase,),
                                 {})):
    __timeout__ = params.LOCAL_TIMEOUT if not sysinfo.RUNNING_ON_CI else params.CI_TIMEOUT

    switch_expected = 'default'
    error_fatal = True
    uses_handle_error = True
    close_on_teardown = ()
    __old_subscribers = ()

    def run(self, *args, **kwargs):
        # pylint:disable=arguments-differ
        if self.switch_expected == 'default':
            self.switch_expected = get_switch_expected(self.fullname)
        return BaseTestCase.run(self, *args, **kwargs)

    def setUp(self):
        super(TestCase, self).setUp()
        # Especially if we're running in leakcheck mode, where
        # the same test gets executed repeatedly, we need to update the
        # current time. Tests don't always go through the full event loop,
        # so that doesn't always happen. test__pool.py:TestPoolYYY.test_async
        # tends to show timeouts that are too short if we don't.
        # XXX: Should some core part of the loop call this?
        gevent.get_hub().loop.update_now()
        self.close_on_teardown = []

    def tearDown(self):
        if getattr(self, 'skipTearDown', False):
            return

        cleanup = getattr(self, 'cleanup', _noop)
        cleanup()
        self._error = self._none
        self._tearDownCloseOnTearDown()
        self.close_on_teardown = []
        super(TestCase, self).tearDown()

    def _tearDownCloseOnTearDown(self):
        while self.close_on_teardown:
            to_close = reversed(self.close_on_teardown)
            self.close_on_teardown = []

            for x in to_close:
                close = getattr(x, 'close', x)
                try:
                    close()
                except Exception: # pylint:disable=broad-except
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
        return os.path.splitext(os.path.basename(self.modulename))[0] + '.' + self.testcasename

    _none = (None, None, None)
    # (context, kind, value)
    _error = _none

    def expect_one_error(self):
        self.assertEqual(self._error, self._none)
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
            self.assertIsNotNone(
                ekind,
                "Error must not be none %r" % (error,))
            assert issubclass(ekind, kind), error
        if value is not None:
            if isinstance(value, str):
                self.assertEqual(str(evalue), value)
            else:
                self.assertIs(evalue, value)
        if where_type is not None:
            self.assertIsInstance(econtext, where_type)
        return error

    def assertMonkeyPatchedFuncSignatures(self, mod_name, func_names=(), exclude=()):
        # We use inspect.getargspec because it's the only thing available
        # in Python 2.7, but it is deprecated
        # pylint:disable=deprecated-method,too-many-locals
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

    def assertEqualFlakyRaceCondition(self, a, b):
        try:
            self.assertEqual(a, b)
        except AssertionError:
            flaky.reraiseFlakyTestRaceCondition()

    assertRaisesRegex = getattr(BaseTestCase, 'assertRaisesRegex',
                                getattr(BaseTestCase, 'assertRaisesRegexp'))
