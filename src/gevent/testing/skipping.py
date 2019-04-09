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

import functools
import unittest

from . import sysinfo

def _identity(f):
    return f

def _do_not_skip(reason):
    assert reason
    return _identity


skipOnWindows = _do_not_skip
skipOnAppVeyor = _do_not_skip
skipOnCI = _do_not_skip

skipOnPyPy = _do_not_skip
skipOnPyPyOnCI = _do_not_skip
skipOnPyPy3OnCI = _do_not_skip
skipOnPyPy3 = _do_not_skip
skipOnPyPyOnWindows = _do_not_skip

skipOnPy37 = unittest.skip if sysinfo.PY37 else _do_not_skip

skipOnPurePython = unittest.skip if sysinfo.PURE_PYTHON else _do_not_skip
skipWithCExtensions = unittest.skip if not sysinfo.PURE_PYTHON else _do_not_skip

skipOnLibuv = _do_not_skip
skipOnLibuvOnWin = _do_not_skip
skipOnLibuvOnCI = _do_not_skip
skipOnLibuvOnCIOnPyPy = _do_not_skip
skipOnLibuvOnPyPyOnWin = _do_not_skip
skipOnLibuvOnTravisOnCPython27 = _do_not_skip

skipOnLibev = _do_not_skip

if sysinfo.WIN:
    skipOnWindows = unittest.skip


if sysinfo.RUNNING_ON_APPVEYOR:
    # See comments scattered around about timeouts and the timer
    # resolution available on appveyor (lots of jitter). this
    # seems worse with the 62-bit builds.
    # Note that we skip/adjust these tests only on AppVeyor, not
    # win32---we don't think there's gevent related problems but
    # environment related problems. These can be tested and debugged
    # separately on windows in a more stable environment.
    skipOnAppVeyor = unittest.skip


if sysinfo.RUNNING_ON_CI:
    skipOnCI = unittest.skip


if sysinfo.PYPY:
    skipOnPyPy = unittest.skip
    if sysinfo.RUNNING_ON_CI:
        skipOnPyPyOnCI = unittest.skip

    if sysinfo.WIN:
        skipOnPyPyOnWindows = unittest.skip

    if sysinfo.PYPY3:
        skipOnPyPy3 = unittest.skip
        if sysinfo.RUNNING_ON_CI:
            # Same as above, for PyPy3.3-5.5-alpha and 3.5-5.7.1-beta and 3.5-5.8
            skipOnPyPy3OnCI = unittest.skip


skipUnderCoverage = unittest.skip if sysinfo.RUN_COVERAGE else _do_not_skip

skipIf = unittest.skipIf
skipUnless = unittest.skipUnless

_has_psutil_process = None
def _check_psutil():
    global _has_psutil_process
    if _has_psutil_process is None:
        _has_psutil_process = sysinfo.get_this_psutil_process() is not None
    return _has_psutil_process


def skipWithoutPSUtil(reason):
    # Important: If you use this on classes, you must not use the
    # two-argument form of super()
    reason = "psutil not available: " + reason
    def decorator(test_item):
        # Defer the check until runtime to avoid imports
        if not isinstance(test_item, type):
            f = test_item
            @functools.wraps(test_item)
            def skip_wrapper(*args):
                if not _check_psutil():
                    raise unittest.SkipTest(reason)
                return f(*args)
            test_item = skip_wrapper
        else:
            # given a class, subclass its setUp method to do the same.

            # The trouble with this is that the decorator automatically
            # rebinds to the same name, and if there are two-argument calls
            # like `super(MyClass, self).thing` in the class, we get infinite
            # recursion (because MyClass has been rebound to the object we return.)
            # This is easy to fix on Python 3: use the zero argument `super()`, because
            # the lookup relies not on names but implicit slots.
            #
            # I didn't find a good workaround for this on Python 2, so
            # I'm just forbidding using the two argument super.
            base = test_item
            class SkipWrapper(base):
                def setUp(self):
                    if not _check_psutil():
                        raise unittest.SkipTest(reason)
                    base.setUp(self)

                def _super(self):
                    return super(base, self)
            SkipWrapper.__name__ = test_item.__name__
            SkipWrapper.__module__ = test_item.__module__
            try:
                SkipWrapper.__qualname__ = test_item.__qualname__
            except AttributeError:
                # Python 2
                pass
            test_item = SkipWrapper

        return test_item
    return decorator

if sysinfo.LIBUV:
    skipOnLibuv = unittest.skip

    if sysinfo.RUNNING_ON_CI:
        skipOnLibuvOnCI = unittest.skip
        if sysinfo.PYPY:
            skipOnLibuvOnCIOnPyPy = unittest.skip
    if sysinfo.RUNNING_ON_TRAVIS:
        if sysinfo.CPYTHON:
            if sysinfo.PY27_ONLY:
                skipOnLibuvOnTravisOnCPython27 = unittest.skip

    if sysinfo.WIN:
        skipOnLibuvOnWin = unittest.skip
        if sysinfo.PYPY:
            skipOnLibuvOnPyPyOnWin = unittest.skip
else:
    skipOnLibev = unittest.skip
