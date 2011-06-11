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
ares_configure_command = './configure CONFIG_COMMANDS= CONFIG_FILES='


if sys.platform == 'win32':
    libraries += ['ws2_32']
    define_macros += [('FD_SETSIZE', '1024'), ('_WIN32', '1')]


CORE = Extension(name='gevent.core',
                 sources=['gevent/gevent.core.c'],
                 include_dirs=['libev'],
                 libraries=libraries,
                 define_macros=define_macros)

ARES = Extension(name='gevent.ares',
                 sources=['gevent/gevent.ares.c'],
                 include_dirs=['c-ares'],
                 libraries=libraries,
                 define_macros=define_macros)
ARES.optional = True


if os.path.exists('libev'):
    CORE.define_macros += [('EV_STANDALONE', '1'),
                           ('EV_COMMON', ''),  # we don't use void* data
                           # libev watchers that we don't use currently:
                           ('EV_STAT_ENABLE', '0'),
                           ('EV_CHECK_ENABLE', '0'),
                           ('EV_CLEANUP_ENABLE', '0'),
                           ('EV_EMBED_ENABLE', '0'),
                           ("EV_PERIODIC_ENABLE", '0')]
    #CORE.gcc_options = ['-Wno-unused-variable', '-Wno-unused-result']  # disable warnings from ev.c


def need_configure_ares():
    if sys.platform == 'win32':
        return False
    if not os.path.exists('c-ares/ares_config.h'):
        return True
    if not os.path.exists('c-ares/ares_build.h'):
        return True
    if 'Generated from ares_build.h.in by configure' not in read('c-ares/ares_build.h'):
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
            for prefix,define in defines:
                if line.startswith(prefix):
                    line = '#ifdef __LP64__\n#define %s 8\n#else\n#define %s 4\n#endif' % (define, define)
                    break
        print >>f, line
    f.close()


def configure_ares():
    if need_configure_ares():
        rc = os.system('cd c-ares && %s' % ares_configure_command)
        if rc == 0 and sys.platform == 'darwin':
            make_universal_header('c-ares/ares_build.h', 'CARES_SIZEOF_LONG')
            make_universal_header('c-ares/ares_config.h', 'SIZEOF_LONG', 'SIZEOF_SIZE_T', 'SIZEOF_TIME_T')


if ares_embed:
    ARES.sources += sorted(glob('c-ares/*.c'))
    if sys.platform == 'win32':
        ARES.libraries += ['advapi32']
        ARES.define_macros += [('CARES_STATICLIB', '')]
    else:
        ARES.configure = configure_ares
        ARES.define_macros += [('HAVE_CONFIG_H', '')]
        if sys.platform != 'darwin':
            ARES.libraries += ['rt']
    ARES.define_macros += [('CARES_EMBED', '')]


def need_update(destination, *source):
    if not os.path.exists(destination):
        sys.stderr.write('Creating %s\n' % destination)
        return True
    dest_mtime = os.stat(destination).st_mtime
    source = source + ('setup.py', )
    for pattern in source:
        for filename in glob(pattern):
            if os.stat(filename).st_mtime - dest_mtime > 1:
                sys.stderr.write('Updating %s (changed: %s)\n' % (destination, filename))
                return True


def system(command):
    sys.stderr.write(command + '\n')
    return os.system(command)


def replace_in_file(filename, old, new, check=True):
    olddata = open(filename).read()
    newdata = olddata.replace(old, new)
    if check:
        assert olddata != newdata, 'replacement in %s failed' % filename
    open(filename, 'w').write(newdata)


def run_cython_core(cython_command):
    if need_update('gevent/core.pyx', 'gevent/core_.pyx'):
        system('m4 gevent/core_.pyx > core.pyx && mv core.pyx gevent/')
    if need_update('gevent/gevent.core.c', 'gevent/core.p*x*', 'gevent/libev.pxd'):
        if 0 == system('%s gevent/core.pyx -o gevent.core.c && mv gevent.core.* gevent/' % (cython_command, )):
            replace_in_file('gevent/gevent.core.c', '\n\n#endif /* Py_PYTHON_H */', '\n#include "callbacks.c"\n#endif /* Py_PYTHON_H */')
            short_path = 'gevent/'
            full_path = join(os.getcwd(), short_path)
            replace_in_file('gevent/gevent.core.c', short_path, full_path, check=False)
            replace_in_file('gevent/gevent.core.h', short_path, full_path, check=False)
    if need_update('gevent/gevent.core.c', 'gevent/callbacks.*', 'gevent/libev*.h', 'libev/*.*'):
        os.system('touch gevent/gevent.core.c')


def run_cython_ares(cython_command):
    if need_update('gevent/gevent.ares.c', 'gevent/ares.pyx'):
        system('%s gevent/ares.pyx -o gevent.ares.c && mv gevent.ares.* gevent/' % cython_command)
    if need_update('gevent/gevent.ares.c', 'gevent/dnshelper.c', 'gevent/inet_ntop.c', 'c-ares/*.*'):
        os.system('touch gevent/gevent.ares.c')


CORE.run_cython = run_cython_core
ARES.run_cython = run_cython_ares


class my_build_ext(build_ext):
    user_options = (build_ext.user_options
                    + [("cython=", None, "path to the cython executable")])

    def initialize_options(self):
        build_ext.initialize_options(self)
        self.cython = "cython"

    def gevent_prepare(self, ext):
        if self.cython:
            run_cython = getattr(ext, 'run_cython', None)
            if run_cython:
                run_cython(self.cython)
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


def read(name):
    try:
        return open(join(dirname(__file__), name)).read()
    except OSError:
        return ''


ext_modules = [CORE, ARES]
warnings = []

def warn(message):
    message += '\n'
    sys.stderr.write(message)
    warnings.append(message)


ARES.disabled_why = None
for filename in ARES.sources:
    if not os.path.exists(filename):
        ARES.disabled_why = '%s does not exist' % filename
        ext_modules.remove(ARES)
        break


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
    if sys.argv[1:] == ['cython']:
        CORE.run_cython('cython')
        ARES.run_cython('cython')
    else:
        try:
            run_setup(ext_modules)
        except BuildFailed:
            if ARES not in ext_modules:
                raise
            ext_modules.remove(ARES)
            ARES.disabled_why = 'failed to build'
            run_setup(ext_modules)
    if ARES.disabled_why:
        sys.stderr.write('\nWARNING: The gevent.ares extension has been disabled because %s.\n' % ARES.disabled_why)
