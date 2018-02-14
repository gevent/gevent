# -*- coding: utf-8 -*-
"""
gevent build utilities.
"""

from __future__ import print_function, absolute_import, division

import re
import os
import os.path
import sys
from subprocess import check_call
from glob import glob

from setuptools import Extension as _Extension
from setuptools.command.build_ext import build_ext


## Exported configurations

PYPY = hasattr(sys, 'pypy_version_info')
WIN = sys.platform.startswith('win')

RUNNING_ON_TRAVIS = os.environ.get('TRAVIS')
RUNNING_ON_APPVEYOR = os.environ.get('APPVEYOR')
RUNNING_ON_CI = RUNNING_ON_TRAVIS or RUNNING_ON_APPVEYOR



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
SKIP_LIBUV = _parse_environ('GEVENT_NO_LIBUV_BUILD')

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


def _system(cmd, cwd=None, env=None, **kwargs):
    sys.stdout.write('Running %r in %s\n' % (cmd, cwd or os.getcwd()))
    sys.stdout.flush()
    if 'shell' not in kwargs:
        kwargs['shell'] = True
    env = env or os.environ.copy()
    if env.get('CC', '').startswith('ccache '):
        # Running configure scripts under ccache just adds overhead.
        env['CC'] = env['CC'][7:]
    return check_call(cmd, cwd=cwd, env=env, **kwargs)


def system(cmd, cwd=None, env=None, **kwargs):
    if _system(cmd, cwd=cwd, env=env, **kwargs):
        sys.exit(1)


# Cython


try:
    from Cython.Build import cythonize
except ImportError:
    # The .c files had better already exist. Based on code from
    # http://cython.readthedocs.io/en/latest/src/reference/compilation.html#distributing-cython-modules
    def cythonize(extensions, **_kwargs):
        for extension in extensions:
            sources = []
            for sfile in extension.sources:
                path, ext = os.path.splitext(sfile)
                if ext in ('.pyx', '.py'):
                    ext = '.c'
                    sfile = path + ext
                sources.append(sfile)
            extension.sources[:] = sources
        return extensions

def cythonize1(ext):
    new_ext = cythonize([ext], include_path=['src/gevent', 'src/gevent/libev', 'src/gevent/resolver'])[0]
    for optional_attr in ('configure', 'optional'):
        if hasattr(ext, optional_attr):
            setattr(new_ext, optional_attr,
                    getattr(ext, optional_attr))
    return new_ext


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




class Extension(_Extension):
    # This class exists currently mostly to make pylint
    # happy in terms of attributes we use.

    def __init__(self, *args, **kwargs):
        self.libraries = []
        self.define_macros = []
        # Python 2 has this as an old-style class for some reason
        # so super() doesn't work.
        _Extension.__init__(self, *args, **kwargs) # pylint:disable=no-member,non-parent-init-called
