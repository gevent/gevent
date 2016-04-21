# -*- coding: utf-8 -*-
"""
libuv build utilities.
"""

from __future__ import print_function, absolute_import, division

import ast
import os
import platform
import subprocess
import sys

from _setuputils import WIN
from _setuputils import DEFINE_MACROS
from _setuputils import Extension
from _setuputils import dep_abspath
from _setuputils import system
from _setuputils import glob_many
from _setuputils import should_embed
from _setuputils import _parse_environ

from distutils import log # pylint:disable=no-name-in-module
from distutils.errors import DistutilsError # pylint: disable=no-name-in-module,import-error

# Inspired by code from https://github.com/saghul/pyuv

LIBUV_EMBED = should_embed('libuv')

if WIN and not LIBUV_EMBED:
    raise DistutilsError('using a system provided libuv is unsupported on Windows')

LIBUV_INCLUDE_DIR = dep_abspath('libuv', 'include')
# Set this to force dynamic linking of libuv, even when building the
# embedded copy. This is most useful when upgrading/changing libuv
# in place.
LIBUV_DYNAMIC_EMBED = _parse_environ("GEVENT_LIBUV_DYNAMIC_EMBED")
if LIBUV_DYNAMIC_EMBED is None:
    # Not set in the environment. Are we developing?
    # This is convenient for my workflow
    # XXX Is there a better way to get this?
    # This probably doesn't work for 'pip install -e .'
    # or dev-requirments.txt
    if 'develop' in sys.argv:
        LIBUV_DYNAMIC_EMBED = LIBUV_EMBED

LIBUV_LIBRARIES = []
if sys.platform.startswith('linux'):
    LIBUV_LIBRARIES.append('rt')
elif WIN:
    LIBUV_LIBRARIES.append('advapi32')
    LIBUV_LIBRARIES.append('iphlpapi')
    LIBUV_LIBRARIES.append('psapi')
    LIBUV_LIBRARIES.append('shell32')
    LIBUV_LIBRARIES.append('userenv')
    LIBUV_LIBRARIES.append('ws2_32')
elif sys.platform.startswith('freebsd'):
    LIBUV_LIBRARIES.append('kvm')

if not LIBUV_EMBED or LIBUV_DYNAMIC_EMBED:
    LIBUV_LIBRARIES.append('uv')

def prepare_windows_env(env):
    env.pop('VS140COMNTOOLS', None)
    env.pop('VS120COMNTOOLS', None)
    env.pop('VS110COMNTOOLS', None)
    if sys.version_info < (3, 3):
        env.pop('VS100COMNTOOLS', None)
        env['GYP_MSVS_VERSION'] = '2008'
    else:
        env['GYP_MSVS_VERSION'] = '2010'

    if not env.get('PYTHON', '').endswith('.exe'):
        env.pop('PYTHON', None)

    if env.get('PYTHON'):
        log.info("Using python from env %s", env['PYTHON'])
        return  # Already manually set by user.

    if sys.version_info[:2] == (2, 7):
        env['PYTHON'] = sys.executable
        return  # The current executable is fine.

    # Try if `python` on PATH is the right one. If we would execute
    # `python` directly the current executable might be used so we
    # delegate this to cmd.
    cmd = ['cmd.exe', '/C', 'python', '-c', 'import sys; '
           'v = str(sys.version_info[:2]); sys.stdout.write(v); '
           'sys.stdout.flush()']
    try:
        sub = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdout, _ = sub.communicate()
        version = ast.literal_eval(stdout.decode(sys.stdout.encoding).strip()) # pylint:disable=no-member
        if version == (2, 7):
            return  # Python on PATH is fine
    except OSError:
        pass

    # Check default install locations
    path = os.path.join('%SYSTEMDRIVE%', 'Python27', 'python.exe')
    path = os.path.expandvars(path)
    if os.path.isfile(path):
        log.info('Using "%s" to build libuv...' % path)
        env['PYTHON'] = path
        # Things needed for run_with_env.cmd
        # What we're building for, not what we're building with
        # (because it's just the C library)
        env['PYTHON_VERSION'] = str(sys.version_info[0]) + '.' + str(sys.version_info[1]) + ".x"
        # XXX: Just guessing here. Is PYTHON_ARCH correct?
        if 'PYTHON_ARCH' not in env:
            env['PYTHON_ARCH'] = '64' if platform.architecture()[0] == '64bit' else '32'
        from distutils.msvc9compiler import query_vcvarsall
        if sys.version_info[:2] >= (3, 5):
            version = 14
        else:
            version = 9 # for 2.7, but probably not right for 3.4?

        env.update(query_vcvarsall(version))
    else:
        raise DistutilsError('No appropriate Python version found. An '
                             'installation of 2.7 is required to '
                             'build libuv. You can set the environment '
                             'variable "PYTHON" to point to a custom '
                             'installation location.')

# This is a dummy extension that serves to let us hook into
# when we need to compile libuv
LIBUV = Extension(name='gevent.libuv._libuv',
                  sources=['src/gevent/libuv/_libuv.c'],
                  include_dirs=[LIBUV_INCLUDE_DIR],
                  libraries=LIBUV_LIBRARIES,
                  define_macros=list(DEFINE_MACROS),
                  depends=glob_many('deps/libuv/src/*.[ch]'))

if LIBUV_EMBED:
    libuv_dir = dep_abspath('libuv')
    if WIN:
        libuv_library_dir = os.path.join(libuv_dir, 'Release', 'lib')
        libuv_lib = os.path.join(libuv_library_dir, 'libuv.lib')
        LIBUV.extra_link_args.extend(['/NODEFAULTLIB:libcmt', '/LTCG'])
        LIBUV.extra_objects.append(libuv_lib)
    else:
        libuv_library_dir = os.path.join(libuv_dir, '.libs')
        libuv_lib = os.path.join(libuv_library_dir, 'libuv.a')
        if not LIBUV_DYNAMIC_EMBED:
            LIBUV.extra_objects.append(libuv_lib)
        else:
            LIBUV.library_dirs.append(libuv_library_dir)
            LIBUV.extra_link_args.extend(["-Wl,-rpath", libuv_library_dir])

def configure_libuv(_bext, _ext):
    def build_libuv():
        cflags = '-fPIC'
        env = os.environ.copy()
        env['CFLAGS'] = ' '.join(x for x in (cflags,
                                             env.get('CFLAGS', None),
                                             env.get('ARCHFLAGS', None))
                                 if x)
        # Since we're building a static library, if link-time-optimization is requested, it
        # results in failure to properly create the library archive. This goes unnoticed on
        # OS X until import time because of '-undefined dynamic_lookup'. On the raspberry
        # pi, it causes the linker to crash
        if '-flto' in env['CFLAGS']:
            log.info("Removing LTO")
            env['CFLAGS'] = env['CFLAGS'].replace('-flto', '')
        log.info('Building libuv with cflags %s', env['CFLAGS'])
        if WIN:
            prepare_windows_env(env)
            libuv_arch = {'32bit': 'x86', '64bit': 'x64'}[platform.architecture()[0]]
            system(["cmd", "/E:ON", "/V:ON", "/C", "..\\..\\appveyor\\run_with_env.cmd",
                    'vcbuild.bat', libuv_arch, 'release'],
                   cwd=libuv_dir,
                   env=env,
                   shell=False)
        else:
            # autogen: requires automake and libtool installed
            system(['./autogen.sh'],
                   cwd=libuv_dir,
                   env=env)
            # On OS X, the linker will link to the full path
            # of the library libuv *as encoded in the dylib it finds*.
            # So the libdir is important and must match the actual location
            # of the dynamic library if we want to dynamically link to it.
            # Otherwise, we wind up linking to /usr/local/lib/libuv.dylib by
            # default, which can't be found. `otool -D libuv.dylib` will show
            # this name, and `otool -L src/gevent/libuv/_corecffi.so` will show
            # what got linked. Note that this approach results in libuv.dylib
            # apparently linking to *itself*, which is weird, but not harmful
            system(['./configure', '--libdir=' + libuv_library_dir],
                   cwd=libuv_dir,
                   env=env)
            system(['make'],
                   cwd=libuv_dir,
                   env=env)

    if not os.path.exists(libuv_lib):
        log.info('libuv needs to be compiled.')
        build_libuv()
    else:
        log.info('No need to build libuv.')

if LIBUV_EMBED:
    LIBUV.configure = configure_libuv
