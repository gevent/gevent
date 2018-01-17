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

import os.path

import gevent

from greentest import sysinfo
from greentest import six

OPTIONAL_MODULES = ['resolver_ares']


def walk_modules(basedir=None, modpath=None, include_so=False, recursive=False):
    # pylint:disable=too-many-branches
    if sysinfo.PYPY:
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
        elif include_so and fn.endswith(sysinfo.SHARED_OBJECT_EXTENSION):
            if '.pypy-' in fn:
                continue
            if fn.endswith('_d.so'):
                yield path, modpath + fn[:-5]
            else:
                yield path, modpath + fn[:-3]
