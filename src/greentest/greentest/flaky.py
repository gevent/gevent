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
import unittest

from gevent.util import dump_stacks

from greentest import sysinfo
from greentest import six

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

if sysinfo.RUNNING_ON_CI:
    # pylint: disable=function-redefined
    def reraiseFlakyTestRaceCondition():
        six.reraise(FlakyTestRaceCondition,
                    FlakyTestRaceCondition('\n'.join(dump_stacks())),
                    sys.exc_info()[2])

    def reraiseFlakyTestTimeout():
        six.reraise(FlakyTestTimeout,
                    FlakyTestTimeout(),
                    sys.exc_info()[2])

    if sysinfo.LIBUV:
        reraiseFlakyTestRaceConditionLibuv = reraiseFlakyTestRaceCondition
        reraiseFlakyTestTimeoutLibuv = reraiseFlakyTestTimeout
