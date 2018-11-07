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

import os
import unittest
import re

from . import sysinfo

# Linux/OS X/BSD platforms can implement this by calling out to lsof


if sysinfo.WIN:
    def _run_lsof():
        raise unittest.SkipTest("lsof not expected on Windows")
else:
    def _run_lsof():
        import tempfile
        pid = os.getpid()
        fd, tmpname = tempfile.mkstemp('get_open_files')
        os.close(fd)
        lsof_command = 'lsof -p %s > %s' % (pid, tmpname)
        if os.system(lsof_command):
            # XXX: This prints to the console an annoying message: 'lsof is not recognized'
            raise unittest.SkipTest("lsof failed")
        with open(tmpname) as fobj:
            data = fobj.read().strip()
        os.remove(tmpname)
        return data

def default_get_open_files(pipes=False):
    data = _run_lsof()
    results = {}
    for line in data.split('\n'):
        line = line.strip()
        if not line or line.startswith("COMMAND"):
            # Skip header and blank lines
            continue
        split = re.split(r'\s+', line)
        _command, _pid, _user, fd = split[:4]
        # Pipes (on OS X, at least) get an fd like "3" while normal files get an fd like "1u"
        if fd[:-1].isdigit() or fd.isdigit():
            if not pipes and fd[-1].isdigit():
                continue
            fd = int(fd[:-1]) if not fd[-1].isdigit() else int(fd)
            if fd in results:
                params = (fd, line, split, results.get(fd), data)
                raise AssertionError('error when parsing lsof output: duplicate fd=%r\nline=%r\nsplit=%r\nprevious=%r\ndata:\n%s' % params)
            results[fd] = line
    if not results:
        raise AssertionError('failed to parse lsof:\n%s' % (data, ))
    results['data'] = data
    return results

def default_get_number_open_files():
    if os.path.exists('/proc/'):
        # Linux only
        fd_directory = '/proc/%d/fd' % os.getpid()
        return len(os.listdir(fd_directory))

    try:
        return len(get_open_files(pipes=True)) - 1
    except (OSError, AssertionError, unittest.SkipTest):
        return 0

lsof_get_open_files = default_get_open_files

try:
    # psutil import subprocess which on Python 3 imports selectors.
    # This can expose issues with monkey-patching.
    import psutil
except ImportError:
    get_open_files = default_get_open_files
    get_number_open_files = default_get_number_open_files
else:
    # If psutil is available (it is cross-platform) use that.
    # It is *much* faster than shelling out to lsof each time
    # (Running 14 tests takes 3.964s with lsof and 0.046 with psutil)
    # However, it still doesn't completely solve the issue on Windows: fds are reported
    # as -1 there, so we can't fully check those.

    def get_open_files():
        """
        Return a list of popenfile and pconn objects.

        Note that other than `fd`, they have different attributes.

        .. important:: If you want to find open sockets, on Windows
           and linux, it is important that the socket at least be listening
           (socket.listen(1)). Unlike the lsof implementation, this will only
           return sockets in a state like that.
        """
        results = dict()
        process = psutil.Process()
        results['data'] = process.open_files() + process.connections('all')
        for x in results['data']:
            results[x.fd] = x
        results['data'] += ['From psutil', process]
        return results

    def get_number_open_files():
        process = psutil.Process()
        try:
            return process.num_fds()
        except AttributeError:
            # num_fds is unix only. Is num_handles close enough on Windows?
            return 0
