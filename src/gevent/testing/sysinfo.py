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

import os
import sys

import gevent.core
from gevent import _compat as gsysinfo

VERBOSE = sys.argv.count('-v') > 1

# Python implementations
PYPY = gsysinfo.PYPY
CPYTHON = not PYPY

# Platform/operating system
WIN = gsysinfo.WIN
LINUX = gsysinfo.LINUX
OSX = gsysinfo.OSX

PURE_PYTHON = gsysinfo.PURE_PYTHON

get_this_psutil_process = gsysinfo.get_this_psutil_process

# XXX: Formalize this better
LIBUV = 'libuv' in gevent.core.loop.__module__ # pylint:disable=no-member
CFFI_BACKEND = PYPY or LIBUV or 'cffi' in os.getenv('GEVENT_LOOP', '')

if '--debug-greentest' in sys.argv:
    sys.argv.remove('--debug-greentest')
    DEBUG = True
else:
    DEBUG = False

RUN_LEAKCHECKS = os.getenv('GEVENTTEST_LEAKCHECK')
RUN_COVERAGE = os.getenv("COVERAGE_PROCESS_START") or os.getenv("GEVENTTEST_COVERAGE")

# Generally, ignore the portions that are only implemented
# on particular platforms; they generally contain partial
# implementations completed in different modules.
PLATFORM_SPECIFIC_SUFFIXES = ('2', '279', '3')
if WIN:
    PLATFORM_SPECIFIC_SUFFIXES += ('posix',)

PY2 = None
PY3 = None
PY35 = None
PY36 = None
PY37 = None
PY38 = None

NON_APPLICABLE_SUFFIXES = ()
if sys.version_info[0] >= 3:
    # Python 3
    NON_APPLICABLE_SUFFIXES += ('2', '279')
    PY2 = False
    PY3 = True
    if sys.version_info[1] >= 5:
        PY35 = True
    if sys.version_info[1] >= 6:
        PY36 = True
    if sys.version_info[1] >= 7:
        PY37 = True
    if sys.version_info[1] >= 8:
        PY38 = True

elif sys.version_info[0] == 2:
    # Any python 2
    PY3 = False
    PY2 = True
    NON_APPLICABLE_SUFFIXES += ('3',)
    if (sys.version_info[1] < 7
            or (sys.version_info[1] == 7 and sys.version_info[2] < 9)):
        # Python 2, < 2.7.9
        NON_APPLICABLE_SUFFIXES += ('279',)

PYPY3 = PYPY and PY3

PY27_ONLY = sys.version_info[0] == 2 and sys.version_info[1] == 7

PYGTE279 = (
    sys.version_info[0] == 2
    and sys.version_info[1] >= 7
    and sys.version_info[2] >= 9
)

if WIN:
    NON_APPLICABLE_SUFFIXES += ("posix",)
    # This is intimately tied to FileObjectPosix
    NON_APPLICABLE_SUFFIXES += ("fileobject2",)
    SHARED_OBJECT_EXTENSION = ".pyd"
else:
    SHARED_OBJECT_EXTENSION = ".so"


RUNNING_ON_TRAVIS = os.environ.get('TRAVIS')
RUNNING_ON_APPVEYOR = os.environ.get('APPVEYOR')
RUNNING_ON_CI = RUNNING_ON_TRAVIS or RUNNING_ON_APPVEYOR
RUNNING_ON_MANYLINUX = os.environ.get('GEVENT_MANYLINUX')

if RUNNING_ON_APPVEYOR:
    # We can't exec corecext on appveyor if we haven't run setup.py in
    # 'develop' mode (i.e., we install)
    NON_APPLICABLE_SUFFIXES += ('corecext',)

EXPECT_POOR_TIMER_RESOLUTION = (
    PYPY3
    or RUNNING_ON_APPVEYOR
    or (LIBUV and PYPY)
    or RUN_COVERAGE
    or (OSX and RUNNING_ON_CI)
)


CONN_ABORTED_ERRORS = []
try:
    from errno import WSAECONNABORTED
    CONN_ABORTED_ERRORS.append(WSAECONNABORTED)
except ImportError:
    pass

from errno import ECONNRESET
CONN_ABORTED_ERRORS.append(ECONNRESET)

CONN_ABORTED_ERRORS = frozenset(CONN_ABORTED_ERRORS)

RESOLVER_ARES = os.getenv('GEVENT_RESOLVER') == 'ares'
RESOLVER_DNSPYTHON = os.getenv('GEVENT_RESOLVER') == 'dnspython'

RESOLVER_NOT_SYSTEM = RESOLVER_ARES or RESOLVER_DNSPYTHON

def get_python_version():
    """
    Return a string of the simple python version,
    such as '3.8.0b4'. Handles alpha and beta and final releases.
    """
    version = '%s.%s.%s' % sys.version_info[:3]
    if sys.version_info[3] == 'alpha':
        version += 'a%s' % sys.version_info[4]
    elif sys.version_info[3] == 'beta':
        version += 'b%s' % sys.version_info[4]

    return version

def libev_supports_linux_aio():
    # libev requires kernel 4.19 or above to be able to support
    # linux AIO. It can still be compiled in, but will fail to create
    # the loop at runtime.
    from distutils.version import LooseVersion
    from platform import system
    from platform import release

    return system() == 'Linux' and LooseVersion(release() or '0') >= LooseVersion('4.19')
