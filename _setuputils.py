# -*- coding: utf-8 -*-
"""
gevent build utilities.

.. $Id$
"""

from __future__ import print_function, absolute_import, division

import re
import os
import os.path
import sys
from subprocess import check_call
from glob import glob

from setuptools.command.build_ext import build_ext
from setuptools.command.sdist import sdist

## Exported configurations

PYPY = hasattr(sys, 'pypy_version_info')
WIN = sys.platform.startswith('win')
CFFI_WIN_BUILD_ANYWAY = os.environ.get("PYPY_WIN_BUILD_ANYWAY")

LIBRARIES = []
DEFINE_MACROS = []


if WIN:
    LIBRARIES += ['ws2_32']
    DEFINE_MACROS += [('FD_SETSIZE', '1024'), ('_WIN32', '1')]

### File handling

THIS_DIR = os.path.dirname(__file__)

def quoted_abspath(*segments):
    return '"' + os.path.abspath(os.path.join(*segments)) + '"'

def read(name, *args):
    """Read a file path relative to this file."""
    with open(os.path.join(THIS_DIR, name)) as f:
        return f.read(*args)

def read_version(name="src/gevent/__init__.py"):
    contents = read(name)
    version = re.search(r"__version__\s*=\s*'(.*)'", contents, re.M).group(1)
    assert version, "could not read version"
    return version

def dep_abspath(depname, *extra):
    return os.path.abspath(os.path.join('deps', depname, *extra))

def quoted_dep_abspath(depname):
    return quoted_abspath(dep_abspath(depname))

def glob_many(*globs):
    """
    Return a list of all the glob patterns expanded.
    """
    result = []
    for pattern in globs:
        result.extend(glob(pattern))
    return sorted(result)


## Configuration

def _parse_environ(key):
    value = os.environ.get(key)
    if not value:
        return
    value = value.lower().strip()
    if value in ('1', 'true', 'on', 'yes'):
        return True
    elif value in ('0', 'false', 'off', 'no'):
        return False
    raise ValueError('Environment variable %r has invalid value %r. '
                     'Please set it to 1, 0 or an empty string' % (key, value))

IGNORE_CFFI = _parse_environ("GEVENT_NO_CFFI_BUILD")

def _get_config_value(key, defkey, path=None):
    """
    Find a boolean value, configured in the environment at *key* or
    *defkey* (typically, *defkey* will be shared by several calls). If
    those don't exist, then check for the existence of *path* and return
    that (if path is given)
    """
    value = _parse_environ(key)
    if value is None:
        value = _parse_environ(defkey)
    if value is not None:
        return value
    return os.path.exists(path) if path is not None else False

def should_embed(dep_name):
    """
    Check the configuration for the dep_name and see if it
    should be embedded. Environment keys are derived from the
    dep name: libev becomes LIBEV_EMBED and c-ares becomes CARES_EMBED.
    """
    path = dep_abspath(dep_name)
    defkey = 'EMBED'
    key = dep_name.replace('-', '').upper() + '_' + defkey

    return _get_config_value(key, defkey, path)

## Headers

def make_universal_header(filename, *defines):
    defines = [('#define %s ' % define, define) for define in defines]
    with open(filename, 'r') as f:
        lines = f.read().split('\n')
    ifdef = 0
    with open(filename, 'w') as f:
        for line in lines:
            if line.startswith('#ifdef'):
                ifdef += 1
            elif line.startswith('#endif'):
                ifdef -= 1
            elif not ifdef:
                for prefix, define in defines:
                    if line.startswith(prefix):
                        line = '#ifdef __LP64__\n#define %s 8\n#else\n#define %s 4\n#endif' % (define, define)
                        break
            print(line, file=f)

# Processes


def _system(cmd):
    sys.stdout.write('Running %r in %s\n' % (cmd, os.getcwd()))
    return check_call(cmd, shell=True)


def system(cmd):
    if _system(cmd):
        sys.exit(1)


## Distutils extensions
class BuildFailed(Exception):
    pass

from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError # pylint:disable=no-name-in-module,import-error
ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError, IOError)


class ConfiguringBuildExt(build_ext):

    def gevent_prepare(self, ext):
        configure = getattr(ext, 'configure', None)
        if configure:
            configure(self, ext)

    def build_extension(self, ext):
        self.gevent_prepare(ext)
        try:
            result = build_ext.build_extension(self, ext)
        except ext_errors:
            if getattr(ext, 'optional', False):
                raise BuildFailed()
            else:
                raise
        return result


class MakeSdist(sdist):
    """
    An sdist that runs make if needed, and makes sure
    that the Makefile doesn't make it into the dist
    archive.
    """

    _ran_make = False

    @classmethod
    def make(cls, targets=''):
        # NOTE: We have two copies of the makefile, one
        # for posix, one for windows. Our sdist command takes
        # care of renaming the posix one so it doesn't get into
        # the .tar.gz file (we don't want to re-run make in a released
        # file). We trigger off the presence/absence of that file altogether
        # to skip both posix and unix branches.
        # See https://github.com/gevent/gevent/issues/757
        if cls._ran_make:
            return

        if os.path.exists('Makefile'):
            if WIN:
                # make.cmd handles checking for PyPy and only making the
                # right things, so we can ignore the targets
                system("appveyor\\make.cmd")
            else:
                if "PYTHON" not in os.environ:
                    os.environ["PYTHON"] = sys.executable
                # Let the user specify the make program, helpful for BSD
                # where GNU make might be called gmake
                make_program = os.environ.get('MAKE', 'make')
                system(make_program + ' ' + targets)
        cls._ran_make = True

    def run(self):
        renamed = False
        if os.path.exists('Makefile'):
            self.make()
            os.rename('Makefile', 'Makefile.ext')
            renamed = True
        try:
            return sdist.run(self)
        finally:
            if renamed:
                os.rename('Makefile.ext', 'Makefile')


from setuptools import Extension as _Extension

class Extension(_Extension):
    # This class exists currently mostly to make pylint
    # happy in terms of attributes we use.

    def __init__(self, *args, **kwargs):
        self.libraries = []
        self.define_macros = []
        # Python 2 has this as an old-style class for some reason
        # so super() doesn't work.
        _Extension.__init__(self, *args, **kwargs) # pylint:disable=no-member,non-parent-init-called
