# Copyright (c) 2008-2009 AG Projects
# Copyright 2018 gevent community
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

import unittest

# pylint:disable=unused-import

from greentest.sysinfo import VERBOSE
from greentest.sysinfo import WIN
from greentest.sysinfo import LINUX
from greentest.sysinfo import LIBUV
from greentest.sysinfo import CFFI_BACKEND
from greentest.sysinfo import DEBUG
from greentest.sysinfo import RUN_LEAKCHECKS
from greentest.sysinfo import RUN_COVERAGE

from greentest.sysinfo import PY2
from greentest.sysinfo import PY3
from greentest.sysinfo import PY34
from greentest.sysinfo import PY36
from greentest.sysinfo import PY37

from greentest.sysinfo import PYPY
from greentest.sysinfo import PYPY3
from greentest.sysinfo import CPYTHON

from greentest.sysinfo import PLATFORM_SPECIFIC_SUFFIXES
from greentest.sysinfo import NON_APPLICABLE_SUFFIXES
from greentest.sysinfo import SHARED_OBJECT_EXTENSION

from greentest.sysinfo import RUNNING_ON_TRAVIS
from greentest.sysinfo import RUNNING_ON_APPVEYOR
from greentest.sysinfo import RUNNING_ON_CI

from greentest.sysinfo import RESOLVER_NOT_SYSTEM
from greentest.sysinfo import RESOLVER_DNSPYTHON
from greentest.sysinfo import RESOLVER_ARES

from greentest.sysinfo import EXPECT_POOR_TIMER_RESOLUTION

from greentest.sysinfo import CONN_ABORTED_ERRORS

from greentest.skipping import skipOnWindows
from greentest.skipping import skipOnAppVeyor
from greentest.skipping import skipOnCI
from greentest.skipping import skipOnPyPy3OnCI
from greentest.skipping import skipOnPyPy
from greentest.skipping import skipOnPyPyOnCI
from greentest.skipping import skipOnPyPy3
from greentest.skipping import skipIf
from greentest.skipping import skipOnLibuv
from greentest.skipping import skipOnLibuvOnWin
from greentest.skipping import skipOnLibuvOnCI
from greentest.skipping import skipOnLibuvOnCIOnPyPy
from greentest.skipping import skipOnLibuvOnPyPyOnWin
from greentest.skipping import skipOnPurePython
from greentest.skipping import skipWithCExtensions


from greentest.exception import ExpectedException


from greentest.leakcheck import ignores_leakcheck



from greentest.params import LARGE_TIMEOUT

from greentest.params import DEFAULT_LOCAL_HOST_ADDR
from greentest.params import DEFAULT_LOCAL_HOST_ADDR6
from greentest.params import DEFAULT_BIND_ADDR


from greentest.params import DEFAULT_SOCKET_TIMEOUT
from greentest.params import DEFAULT_XPC_SOCKET_TIMEOUT

main = unittest.main

from greentest.hub import QuietHub

import gevent.hub
gevent.hub.Hub = QuietHub


from greentest.sockets import bind_and_listen
from greentest.sockets import tcp_listener

from greentest.openfiles import get_number_open_files
from greentest.openfiles import get_open_files

from greentest.testcase import TestCase

from greentest.modules import walk_modules

BaseTestCase = unittest.TestCase

from greentest.flaky import reraiseFlakyTestTimeout
from greentest.flaky import reraiseFlakyTestRaceCondition
