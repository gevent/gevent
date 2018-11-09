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


from .sysinfo import PY3
from .sysinfo import PYPY
from .sysinfo import WIN
from .sysinfo import LIBUV
from .sysinfo import OSX

from .sysinfo import RUNNING_ON_TRAVIS
from .sysinfo import RUNNING_ON_APPVEYOR
from .sysinfo import EXPECT_POOR_TIMER_RESOLUTION
from .sysinfo import RESOLVER_ARES


# Travis is slow and overloaded; Appveyor used to be faster, but
# as of Dec 2015 it's almost always slower and/or has much worse timer
# resolution
CI_TIMEOUT = 15
if (PY3 and PYPY) or (PYPY and WIN and LIBUV):
    # pypy3 is very slow right now,
    # as is PyPy2 on windows (which only has libuv)
    CI_TIMEOUT = 20
if PYPY and LIBUV:
    # slow and flaky timeouts
    LOCAL_TIMEOUT = CI_TIMEOUT
else:
    LOCAL_TIMEOUT = 1

LARGE_TIMEOUT = max(LOCAL_TIMEOUT, CI_TIMEOUT)

DEFAULT_LOCAL_HOST_ADDR = 'localhost'
DEFAULT_LOCAL_HOST_ADDR6 = DEFAULT_LOCAL_HOST_ADDR
DEFAULT_BIND_ADDR = ''

if RUNNING_ON_TRAVIS:
    # As of November 2017 (probably Sept or Oct), after a
    # Travis upgrade, using "localhost" no longer works,
    # producing 'OSError: [Errno 99] Cannot assign
    # requested address'. This is apparently something to do with
    # docker containers. Sigh.
    DEFAULT_LOCAL_HOST_ADDR = '127.0.0.1'
    DEFAULT_LOCAL_HOST_ADDR6 = '::1'
    # Likewise, binding to '' appears to work, but it cannot be
    # connected to with the same error.
    DEFAULT_BIND_ADDR = '127.0.0.1'

if RUNNING_ON_APPVEYOR:
    DEFAULT_BIND_ADDR = '127.0.0.1'
    DEFAULT_LOCAL_HOST_ADDR = '127.0.0.1'


if RESOLVER_ARES and OSX:
    # Ares likes to raise "malformed domain name" on '', at least
    # on OS X
    DEFAULT_BIND_ADDR = '127.0.0.1'

DEFAULT_CONNECT = DEFAULT_LOCAL_HOST_ADDR
DEFAULT_BIND_ADDR_TUPLE = (DEFAULT_BIND_ADDR, 0)

# For in-process sockets
DEFAULT_SOCKET_TIMEOUT = 0.1 if not EXPECT_POOR_TIMER_RESOLUTION else 2.0

# For cross-process sockets
DEFAULT_XPC_SOCKET_TIMEOUT = 2.0 if not EXPECT_POOR_TIMER_RESOLUTION else 4.0
