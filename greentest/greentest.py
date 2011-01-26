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
import unittest
from unittest import TestCase as BaseTestCase
import time
import traceback
import re
import os
from os.path import basename, splitext
import gevent
from patched_tests_setup import get_switch_expected
try:
    from functools import wraps
except ImportError:
    wraps = lambda *args: (lambda x: x)

VERBOSE = sys.argv.count('-v') > 1

if '--debug-greentest' in sys.argv:
    sys.argv.remove('--debug-greentest')
    DEBUG = True
else:
    DEBUG = False

gettotalrefcount = getattr(sys, 'gettotalrefcount', None)


def wrap(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        import gc
        gc.disable()
        gc.collect()
        deltas = []
        d = None
        try:
            for _ in xrange(4):
                d = gettotalrefcount()
                method(self, *args, **kwargs)
                if hasattr(self, 'cleanup'):
                    self.cleanup()
                if 'urlparse' in sys.modules:
                    sys.modules['urlparse'].clear_cache()
                d = gettotalrefcount() - d
                deltas.append(d)
                if deltas[-1] == 0:
                    break
            else:
                raise AssertionError('refcount increased by %r' % (deltas, ))
        finally:
            gc.collect()
            gc.enable()
    return wrapped


class CheckRefcountMetaClass(type):
    def __new__(meta, classname, bases, classDict):
        if classDict.get('check_totalrefcount', True):
            for key, value in classDict.items():
                if (key.startswith('test_') or key == 'test') and callable(value):
                    classDict.pop(key)
                    classDict[key] = wrap(value)
        return type.__new__(meta, classname, bases, classDict)


class TestCase0(BaseTestCase):

    __timeout__ = 1
    switch_expected = 'default'
    _switch_count = None

    def __init__(self, *args, **kwargs):
        BaseTestCase.__init__(self, *args, **kwargs)
        self._timer = None
        self._hub = gevent.hub.get_hub()
        self._switch_count = None

    def run(self, *args, **kwargs):
        if self.switch_expected == 'default':
            self.switch_expected = get_switch_expected(self.fullname)
        return BaseTestCase.run(self, *args, **kwargs)

    def setUp(self):
        gevent.sleep(0)  # switch at least once to setup signal handlers
        if hasattr(self._hub, 'switch_count'):
            self._switch_count = self._hub.switch_count
        self._timer = gevent.Timeout.start_new(self.__timeout__, RuntimeError('test is taking too long'))

    def tearDown(self):
        if hasattr(self, 'cleanup'):
            self.cleanup()
        try:
            if not hasattr(self, 'stderr'):
                self.unhook_stderr()
            if hasattr(self, 'stderr'):
                sys.__stderr__.write(self.stderr)
        except:
            traceback.print_exc()
        if getattr(self, '_timer', None) is not None:
            self._timer.cancel()
            self._timer = None
            if self._switch_count is not None and hasattr(self._hub, 'switch_count'):
                msg = ''
                if self._hub.switch_count < self._switch_count:
                    msg = 'hub.switch_count decreased?\n'
                elif self._hub.switch_count == self._switch_count:
                    if self.switch_expected:
                        msg = '%s.%s did not switch\n' % (type(self).__name__, self.testname)
                elif self._hub.switch_count > self._switch_count:
                    if not self.switch_expected:
                        msg = '%s.%s switched but expected not to\n' % (type(self).__name__, self.testname)
                if msg:
                    print >> sys.stderr, 'WARNING: ' + msg
        else:
            sys.stderr.write('WARNING: %s.setUp does not call base class setUp\n' % (type(self).__name__, ))

    @property
    def testname(self):
        return getattr(self, '_testMethodName', '') or getattr(self, '_TestCase__testMethodName')

    @property
    def testcasename(self):
        return self.__class__.__name__ + '.' + self.testname

    @property
    def modulename(self):
        test_method = getattr(self, self.testname)
        try:
            return test_method.__func__.func_code.co_filename
        except AttributeError:
            return test_method.im_func.func_code.co_filename

    @property
    def fullname(self):
        return splitext(basename(self.modulename))[0] + '.' + self.testcasename

    def hook_stderr(self):
        if VERBOSE:
            return
        from cStringIO import StringIO
        self.new_stderr = StringIO()
        self.old_stderr = sys.stderr
        sys.stderr = self.new_stderr

    def unhook_stderr(self):
        if VERBOSE:
            return
        try:
            value = self.new_stderr.getvalue()
        except AttributeError:
            return None
        sys.stderr = self.old_stderr
        self.stderr = value
        return value

    def assert_no_stderr(self):
        stderr = self.unhook_stderr()
        assert not stderr, 'Expected no stderr, got:\n__________\n%s\n^^^^^^^^^^\n\n' % (stderr, )

    def assert_stderr_traceback(self, typ, value=None):
        if VERBOSE:
            return
        if isinstance(typ, Exception):
            if value is None:
                value = str(typ)
            typ = typ.__class__.__name__
        else:
            typ = getattr(typ, '__name__', typ)
        stderr = self.unhook_stderr()
        assert stderr is not None, repr(stderr)
        traceback_re = '^Traceback \\(most recent call last\\):\n( +.*?\n)+^(?P<type>\w+): (?P<value>.*?)$'
        self.extract_re(traceback_re, type=typ, value=value)

    def assert_stderr(self, message):
        if VERBOSE:
            return
        exact_re = '^' + message + '.*?\n$.*'
        if re.match(exact_re, self.stderr):
            self.extract_re(exact_re)
        else:
            words_re = '^' + '.*?'.join(message.split()) + '.*?\n$'
            if re.match(words_re, self.stderr):
                self.extract_re(words_re)
            else:
                if message.endswith('...'):
                    another_re = '^' + '.*?'.join(message.split()) + '.*?(\n +.*?$){2,5}\n\n'
                    self.extract_re(another_re)
                else:
                    raise AssertionError('%r did not match:\n%r' % (message, self.stderr))

    def assert_mainloop_assertion(self, message=None):
        self.assert_stderr_traceback('AssertionError', 'Cannot switch to MAINLOOP from MAINLOOP')
        if message is not None:
            self.assert_stderr(message)

    def extract_re(self, regex, **kwargs):
        assert self.stderr is not None
        m = re.search(regex, self.stderr, re.DOTALL | re.M)
        if m is None:
            raise AssertionError('%r did not match:\n%r' % (regex, self.stderr))
        for key, expected_value in kwargs.items():
            real_value = m.group(key)
            if expected_value is not None:
                try:
                    self.assertEqual(real_value, expected_value)
                except AssertionError:
                    print 'failed to process: %s' % self.stderr
                    raise
        if DEBUG:
            ate = '\n#ATE#: ' + self.stderr[m.start(0):m.end(0)].replace('\n', '\n#ATE#: ') + '\n'
            sys.__stderr__.write(ate)
        self.stderr = self.stderr[:m.start(0)] + self.stderr[m.end(0) + 1:]


class TestCase(TestCase0):
    if gettotalrefcount is not None:
        __metaclass__ = CheckRefcountMetaClass


main = unittest.main
_original_Hub = gevent.hub.Hub


class CountingHub(_original_Hub):

    switch_count = 0

    def switch(self):
        self.switch_count += 1
        return _original_Hub.switch(self)

gevent.hub.Hub = CountingHub


def test_outer_timeout_is_not_lost(self):
    timeout = gevent.Timeout.start_new(0.001)
    try:
        try:
            result = self.wait(timeout=1)
        except gevent.Timeout, ex:
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
        result = self.wait(timeout=0.01)
        # join and wait simply returns after timeout expires
        delay = time.time() - start
        assert 0.01 - 0.001 <= delay < 0.01 + 0.01, delay
        assert result is None, repr(result)


class GenericGetTestCase(TestCase):

    def wait(self, timeout):
        raise NotImplementedError('override me in subclass')

    def cleanup(self):
        pass

    test_outer_timeout_is_not_lost = test_outer_timeout_is_not_lost

    def test_raises_timeout_number(self):
        start = time.time()
        self.assertRaises(gevent.Timeout, self.wait, timeout=0.01)
        # get raises Timeout after timeout expired
        delay = time.time() - start
        assert 0.01 - 0.001 <= delay < 0.01 + 0.01 + 0.1, delay
        self.cleanup()

    def test_raises_timeout_Timeout(self):
        start = time.time()
        timeout = gevent.Timeout(0.01)
        try:
            self.wait(timeout=timeout)
        except gevent.Timeout, ex:
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
        except RuntimeError, ex:
            assert ex is error, (ex, error)
        delay = time.time() - start
        assert 0.01 - 0.001 <= delay < 0.01 + 0.01 + 0.1, delay
        self.cleanup()


class ExpectedException(Exception):
    """An exception whose traceback should be ignored"""


def walk_modules(basedir=None, modpath=None, include_so=False):
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
            pkg_init = os.path.join(path, '__init__.py')
            if os.path.exists(pkg_init):
                yield pkg_init, modpath + fn
                for p, m in walk_modules(path, modpath + fn + "."):
                    yield p, m
            continue
        if fn.endswith('.py') and fn not in ['__init__.py', 'core.py']:
            yield path, modpath + fn[:-3]
        elif include_so and fn.endswith('.so'):
            if fn.endswith('_d.so'):
                yield path, modpath + fn[:-5]
            else:
                yield path, modpath + fn[:-3]
