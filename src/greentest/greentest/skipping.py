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

import unittest

from greentest import sysinfo


def _do_not_skip(reason):
    assert reason

    def dec(f):
        return f
    return dec


if sysinfo.WIN:
    skipOnWindows = unittest.skip
else:
    skipOnWindows = _do_not_skip

if sysinfo.RUNNING_ON_APPVEYOR:
    # See comments scattered around about timeouts and the timer
    # resolution available on appveyor (lots of jitter). this
    # seems worse with the 62-bit builds.
    # Note that we skip/adjust these tests only on AppVeyor, not
    # win32---we don't think there's gevent related problems but
    # environment related problems. These can be tested and debugged
    # separately on windows in a more stable environment.
    skipOnAppVeyor = unittest.skip

else:
    skipOnAppVeyor = _do_not_skip

if sysinfo.PYPY3 and sysinfo.RUNNING_ON_CI:
    # Same as above, for PyPy3.3-5.5-alpha and 3.5-5.7.1-beta and 3.5-5.8
    skipOnPyPy3OnCI = unittest.skip
else:
    skipOnPyPy3OnCI = _do_not_skip

if sysinfo.PYPY:
    skipOnPyPy = unittest.skip
else:
    skipOnPyPy = _do_not_skip

if sysinfo.PYPY3:
    skipOnPyPy3 = unittest.skip
else:
    skipOnPyPy3 = _do_not_skip

skipIf = unittest.skipIf


skipOnLibuv = _do_not_skip
skipOnLibuvOnCI = _do_not_skip
skipOnLibuvOnCIOnPyPy = _do_not_skip
skipOnLibuvOnPyPyOnWin = _do_not_skip

if sysinfo.LIBUV:
    skipOnLibuv = unittest.skip

    if sysinfo.RUNNING_ON_CI:
        skipOnLibuvOnCI = unittest.skip
        if sysinfo.PYPY:
            skipOnLibuvOnCIOnPyPy = unittest.skip

    if sysinfo.PYPY and sysinfo.WIN:
        skipOnLibuvOnPyPyOnWin = unittest.skip
