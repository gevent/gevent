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

import sys
import gc
import collections
import types
from functools import wraps

import gevent
import gevent.core


def ignores_leakcheck(func):
    func.ignore_leakcheck = True
    return func

# Some builtin things that we ignore
IGNORED_TYPES = (tuple, dict, types.FrameType, types.TracebackType)
try:
    callback_kind = gevent.core.callback
except AttributeError:
    # Must be using FFI.
    from gevent._ffi.callback import callback as callback_kind

def _type_hist():
    d = collections.defaultdict(int)
    for x in gc.get_objects():
        k = type(x)
        if k in IGNORED_TYPES:
            continue
        if k == callback_kind and x.callback is None and x.args is None:
            # these represent callbacks that have been stopped, but
            # the event loop hasn't cycled around to run them. The only
            # known cause of this is killing greenlets before they get a chance
            # to run for the first time.
            continue
        d[k] += 1
    return d

def _report_diff(a, b):
    diff_lines = []
    for k, v in sorted(a.items(), key=lambda i: i[0].__name__):
        if b[k] != v:
            diff_lines.append("%s: %s != %s" % (k, v, b[k]))

    if not diff_lines:
        return None
    diff = '\n'.join(diff_lines)
    return diff

def wrap_refcount(method):
    if getattr(method, 'ignore_leakcheck', False):
        return method


    @wraps(method)
    def wrapper(self, *args, **kwargs): # pylint:disable=too-many-branches
        gc.collect()
        gc.collect()
        gc.collect()
        deltas = []
        d = None
        gc.disable()

        # The very first time we are called, we have already been
        # self.setUp() by the test runner, so we don't need to do it again.
        needs_setUp = False

        try:
            while True:
                # Grab current snapshot
                hist_before = _type_hist()
                d = sum(hist_before.values())

                if needs_setUp:
                    self.setUp()
                    self.skipTearDown = False
                try:
                    method(self, *args, **kwargs)
                finally:
                    self.tearDown()
                    self.skipTearDown = True
                    needs_setUp = True

                # Grab post snapshot
                if 'urlparse' in sys.modules:
                    sys.modules['urlparse'].clear_cache()
                if 'urllib.parse' in sys.modules:
                    sys.modules['urllib.parse'].clear_cache()
                hist_after = _type_hist()
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
                    diff = _report_diff(hist_before, hist_after)
                    raise AssertionError('refcount increased by %r\n%s' % (deltas, diff))
                # OK, we don't know for sure yet. Let's search for more
                if sum(deltas[-3:]) <= 0 or sum(deltas[-4:]) <= 0 or deltas[-4:].count(0) >= 2:
                    # this is suspicious, so give a few more runs
                    limit = 11
                else:
                    limit = 7
                if len(deltas) >= limit:
                    raise AssertionError('refcount increased by %r\n%s'
                                         % (deltas,
                                            _report_diff(hist_before, hist_after)))
        finally:
            gc.enable()

    return wrapper
