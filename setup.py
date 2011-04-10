#!/usr/bin/env python
"""gevent build & installation script"""
import sys
import os
import re
import traceback
from os.path import join, abspath, basename, dirname

try:
    from setuptools import Extension, setup
except ImportError:
    from distutils.core import Extension, setup
from distutils.command import build_ext

__version__ = re.search("__version__\s*=\s*'(.*)'", open('gevent/__init__.py').read(), re.M).group(1)
assert __version__

libev_embed = os.path.exists('libev')
cares_embed = os.path.exists('c-ares')

cython_output = 'gevent/core.c'
defines = []
include_dirs = []
libraries = []
gcc_options = []
cares_configure_command = './configure CONFIG_COMMANDS= CONFIG_FILES='

if libev_embed:
    defines += [('EV_STANDALONE', '1'),
                ('EV_COMMON', ''),  # we don't use void* data
                # libev watchers that we don't use currently:
                ('EV_STAT_ENABLE', '0'),
                ('EV_CHECK_ENABLE', '0'),
                ('EV_FORK_ENABLE', '0'),
                ('EV_CLEANUP_ENABLE', '0'),
                ('EV_EMBED_ENABLE', '0'),
                ('EV_ASYNC_ENABLE', '0'),
                ("EV_PERIODIC_ENABLE", '0'),
                ("EV_CHILD_ENABLE", '0')]
    include_dirs += ['libev']
    gcc_options += ['-Wno-unused-variable', '-Wno-unused-result']  # disable warnings from ev.c


if cares_embed:
    include_dirs += ['c-ares']
    defines += [('HAVE_CONFIG_H', '')]


if sys.platform == 'win32':
    libraries += ['ws2_32']
    defines += [('FD_SETSIZE', '1024'), ('_WIN32', '1')]


def has_changed(destination, *source):
    from glob import glob
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


def run_cython(cython_command='cython'):
    if has_changed('gevent/core.pyx', 'gevent/core_.pyx', 'gevent/libev.pxd'):
        system('m4 gevent/core_.pyx > core.pyx && mv core.pyx gevent/')
    if has_changed(cython_output, 'gevent/*.p*x*', 'gevent/*.h', 'gevent/*.c', 'libev/*.c', 'c-ares/*.c'):
        if 0 == system('%s gevent/core.pyx -o core.c && mv core.* gevent/' % (cython_command, )):
            data = open(cython_output).read()
            data = data.replace('\n\n#endif /* Py_PYTHON_H */', '\n#include "callbacks.c"\n#endif /* Py_PYTHON_H */')
            full_path = join(os.getcwd(), 'gevent/')
            data = data.replace(full_path, 'gevent/')
            open(cython_output, 'w').write(data)


class my_build_ext(build_ext.build_ext):
    user_options = (build_ext.build_ext.user_options
                    + [("cython=", None, "path to the cython executable")])

    def initialize_options(self):
        build_ext.build_ext.initialize_options(self)
        self.cython = "cython"

    def configure_cares(self):
        if sys.platform != 'win32' and not os.path.exists('c-ares/ares_config.h'):
            os.system('cd c-ares && %s' % cares_configure_command)

    def build_extension(self, ext):
        if self.cython:
            run_cython(self.cython)
        if cares_embed:
            self.configure_cares()
        try:
            if gcc_options and self.compiler.compiler[0] == 'gcc' and '-Wall' in self.compiler.compiler and not gevent_core.extra_compile_args:
                gevent_core.extra_compile_args = gcc_options
        except (IndexError, AttributeError):
            pass
        result = build_ext.build_ext.build_extension(self, ext)
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


gevent_core = Extension(name='gevent.core',
                        sources=[cython_output],
                        include_dirs=include_dirs,
                        libraries=libraries,
                        define_macros=defines)


def read(name):
    return open(join(dirname(__file__), name)).read()


if __name__ == '__main__':
    if sys.argv[1:] == ['cython']:
        run_cython()
    else:
        setup(
            name='gevent',
            version=__version__,
            description='Coroutine-based network library',
            long_description=read('README.rst'),
            author='Denis Bilenko',
            author_email='denis.bilenko@gmail.com',
            url='http://www.gevent.org/',
            packages=['gevent'],
            ext_modules=[gevent_core],
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
