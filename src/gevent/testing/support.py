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
"""
A re-export of the support module from Python's test package, with some
version compatibility shims and overrides.
"""

import sys

# Proxy through, so that changes to this module reflect in the
# real module too. In 3.7, this is natively supported.
# This breaks static analysis (pylint), so we configure pylint
# to ignore this module.

class _Default(object):
    # A descriptor-like object that will
    # only be used if the actual stdlib module
    # doesn't have the value.

    def __init__(self, value):
        self.value = value

class _ModuleProxy(object):

    __slots__ = ('_orig_mod', '_stdlib_support')

    def __init__(self):
        self._orig_mod = sys.modules[__name__]
        self._stdlib_support = None

    def __get_stdlib_support(self):
        if self._stdlib_support is None:
            try:
                # Renamed from test_support in Python 3,
                # *and* in 2.7.14 (but with a BWC module)
                from test import support as stdlib_support
            except ImportError:
                from test import test_support as stdlib_support
            self._stdlib_support = stdlib_support

        return self._stdlib_support

    def __getattr__(self, name):
        try:
            local_val = getattr(self._orig_mod, name)
        except AttributeError:
            return getattr(self.__get_stdlib_support(), name)

        if isinstance(local_val, _Default):
            try:
                return getattr(self.__get_stdlib_support(), name)
            except AttributeError:
                return local_val.value
            return local_val

    def __setattr__(self, name, value):
        if name in _ModuleProxy.__slots__:
            super(_ModuleProxy, self).__setattr__(name, value)
            return
        # Setting it deletes it from this module, so that
        # we then continue to fall through to the original module.
        try:
            delattr(self._orig_mod, name)
        except AttributeError:
            pass

        setattr(self.__get_stdlib_support(), name, value)

# When is this not defined in test.support?
HOSTv6 = _Default('::1')

# Set by resources.setup_resources()
gevent_has_setup_resources = False

sys.modules[__name__] = _ModuleProxy()
