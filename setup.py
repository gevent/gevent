#!/usr/bin/env python
"""gevent build & installation script"""
import sys
import os
import re
import traceback
from os.path import join, abspath, basename, dirname
from glob import glob

try:
    from setuptools import Extension, setup
except ImportError:
    from distutils.core import Extension, setup
from distutils.command.build_ext import build_ext
from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError
ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError, IOError)


__version__ = re.search("__version__\s*=\s*'(.*)'", open('gevent/__init__.py').read(), re.M).group(1)
assert __version__

ares_embed = os.path.exists('c-ares')
define_macros = []
libraries = []
ares_configure_command = [abspath('c-ares/configure'),
                          'CONFIG_COMMANDS=', 'CONFIG_FILES=']


if sys.platform == 'win32':
    libraries += ['ws2_32']
    define_macros += [('FD_SETSIZE', '1024'), ('_WIN32', '1')]


def expand(*lst):
    result = []
    for item in lst:
        for name in sorted(glob(item)):
            result.append(name)
    return result


CORE = Extension(name='gevent.core',
                 sources=['gevent/gevent.core.c'],
                 include_dirs=['libev'],
                 libraries=libraries,
                 define_macros=define_macros,
                 depends=expand('gevent/callbacks.*', 'gevent/libev*.h', 'libev/*.*'))

ARES = Extension(name='gevent.ares',
                 sources=['gevent/gevent.ares.c'],
                 include_dirs=['c-ares'],
                 libraries=libraries,
                 define_macros=define_macros,
                 depends=expand('gevent/dnshelper.c', 'gevent/cares_*.*'))
ARES.optional = True


ext_modules = [CORE, ARES]


if os.path.exists('libev'):
    CORE.define_macros += [('EV_STANDALONE', '1'),
                           ('EV_COMMON', ''),  # we don't use void* data
                           # libev watchers that we don't use currently:
                           ('EV_STAT_ENABLE', '0'),
                           ('EV_CHECK_ENABLE', '0'),
                           ('EV_CLEANUP_ENABLE', '0'),
                           ('EV_EMBED_ENABLE', '0'),
                           ('EV_CHILD_ENABLE', '0'),
                           ("EV_PERIODIC_ENABLE", '0')]


def need_configure_ares():
    if sys.platform == 'win32':
        return False
    if not os.path.exists('c-ares/ares_config.h'):
        return True
    if not os.path.exists('c-ares/ares_build.h'):
        return True
    if 'Generated from ares_build.h.in by configure' not in read('c-ares/ares_build.h', 100):
        return True


def make_universal_header(filename, *defines):
    defines = [('#define %s ' % define, define) for define in defines]
    lines = open(filename, 'r').read().split('\n')
    ifdef = 0
    f = open(filename, 'w')
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
        print >>f, line
    f.close()


def configure_ares():
    if need_configure_ares():
        # restore permissions
        os.chmod(ares_configure_command[0], 493)  # 493 == 0755
        rc = os.system('cd c-ares && %s' % ' '.join(ares_configure_command))
        if rc == 0 and sys.platform == 'darwin':
            make_universal_header('c-ares/ares_build.h', 'CARES_SIZEOF_LONG')
            make_universal_header('c-ares/ares_config.h', 'SIZEOF_LONG', 'SIZEOF_SIZE_T', 'SIZEOF_TIME_T')


if ares_embed:
    ARES.sources += expand('c-ares/*.c')
    if sys.platform == 'win32':
        ARES.libraries += ['advapi32']
        ARES.define_macros += [('CARES_STATICLIB', '')]
    else:
        ARES.configure = configure_ares
        ARES.define_macros += [('HAVE_CONFIG_H', '')]
        if sys.platform != 'darwin':
            ARES.libraries += ['rt']
    ARES.define_macros += [('CARES_EMBED', '')]


def make(done=[]):
    if not done:
        if os.path.exists('Makefile'):
            if os.system('make'):
                sys.exit(1)
        done.append(1)


class my_build_ext(build_ext):

    def gevent_prepare(self, ext):
        make()
        configure = getattr(ext, 'configure', None)
        if configure:
            configure()

    def build_extension(self, ext):
        self.gevent_prepare(ext)
        try:
            result = build_ext.build_extension(self, ext)
        except ext_errors:
            if getattr(ext, 'optional', False):
                raise BuildFailed
            else:
                raise
        # hack: create a symlink from build/../core.so to gevent/core.so
        # to prevent "ImportError: cannot import name core" failures
        try:
            fullname = self.get_ext_fullname(ext.name)
            modpath = fullname.split('.')
            filename = self.get_ext_filename(ext.name)
            filename = os.path.split(filename)[-1]
            if not self.inplace:
                filename = os.path.join(*modpath[:-1] + [filename])
                path_to_build_core_so = abspath(os.path.join(self.build_lib, filename))
                path_to_core_so = abspath(join('gevent', basename(path_to_build_core_so)))
                if path_to_build_core_so != path_to_core_so:
                    try:
                        os.unlink(path_to_core_so)
                    except OSError:
                        pass
                    if hasattr(os, 'symlink'):
                        sys.stderr.write('Linking %s to %s\n' % (path_to_build_core_so, path_to_core_so))
                        os.symlink(path_to_build_core_so, path_to_core_so)
                    else:
                        sys.stderr.write('Copying %s to %s\n' % (path_to_build_core_so, path_to_core_so))
                        import shutil
                        shutil.copyfile(path_to_build_core_so, path_to_core_so)
        except Exception:
            traceback.print_exc()
        return result


class BuildFailed(Exception):
    pass


def read(name, *args):
    try:
        return open(join(dirname(__file__), name)).read(*args)
    except OSError:
        return ''


def run_setup(ext_modules):
    setup(
        name='gevent',
        version=__version__,
        description='Coroutine-based network library',
        long_description=read('README.rst'),
        author='Denis Bilenko',
        author_email='denis.bilenko@gmail.com',
        url='http://www.gevent.org/',
        packages=['gevent'],
        ext_modules=ext_modules,
        cmdclass={'build_ext': my_build_ext},
        install_requires=['greenlet'],
        classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 2.4",
        "Programming Language :: Python :: 2.5",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta"])


if __name__ == '__main__':
    try:
        run_setup(ext_modules)
    except BuildFailed:
        if ARES not in ext_modules:
            raise
        ext_modules.remove(ARES)
        run_setup(ext_modules)
    if ARES not in ext_modules:
        sys.stderr.write('\nWARNING: The gevent.ares extension has been disabled.\n')
