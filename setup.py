#!/usr/bin/env python
"""gevent build & installation script"""
from __future__ import print_function
import sys
import os
import re
import shutil
import traceback
from os.path import join, abspath, basename, dirname
from glob import glob

PYPY = hasattr(sys, 'pypy_version_info')

try:
    from setuptools import Extension, setup
except ImportError:
    if PYPY:
        # need setuptools for include_package_data to work
        raise
    from distutils.core import Extension, setup
from distutils.command.build_ext import build_ext
from distutils.command.sdist import sdist as _sdist
from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError
ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError, IOError)


__version__ = re.search("__version__\s*=\s*'(.*)'", open('gevent/__init__.py').read(), re.M).group(1)
assert __version__


def parse_environ(key):
    value = os.environ.get(key)
    if not value:
        return
    value = value.lower().strip()
    if value in ('1', 'true', 'on', 'yes'):
        return True
    elif value in ('0', 'false', 'off', 'no'):
        return False
    raise ValueError('Environment variable %r has invalid value %r. Please set it to 1, 0 or an empty string' % (key, value))


def get_config_value(key, defkey, path):
    value = parse_environ(key)
    if value is None:
        value = parse_environ(defkey)
    if value is not None:
        return value
    return os.path.exists(path)


LIBEV_EMBED = get_config_value('LIBEV_EMBED', 'EMBED', 'libev')
CARES_EMBED = get_config_value('CARES_EMBED', 'EMBED', 'c-ares')

define_macros = []
libraries = []
libev_configure_command = ' '.join(["/bin/sh", abspath('libev/configure'), '> configure-output.txt'])
ares_configure_command = ' '.join(["/bin/sh", abspath('c-ares/configure'), 'CONFIG_COMMANDS= CONFIG_FILES= > configure-output.txt'])


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
                 sources=['gevent/gevent.corecext.c'],
                 include_dirs=['libev'] if LIBEV_EMBED else [],
                 libraries=libraries,
                 define_macros=define_macros,
                 depends=expand('gevent/callbacks.*', 'gevent/stathelper.c', 'gevent/libev*.h', 'libev/*.*'))
# QQQ libev can also use -lm, however it seems to be added implicitly

ARES = Extension(name='gevent.ares',
                 sources=['gevent/gevent.ares.c'],
                 include_dirs=['c-ares'] if CARES_EMBED else [],
                 libraries=libraries,
                 define_macros=define_macros,
                 depends=expand('gevent/dnshelper.c', 'gevent/cares_*.*'))
ARES.optional = True


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
        print(line, file=f)
    f.close()


def _system(cmd):
    sys.stdout.write('Running %r in %s\n' % (cmd, os.getcwd()))
    return os.system(cmd)


def system(cmd):
    if _system(cmd):
        sys.exit(1)


def configure_libev(bext, ext):
    if sys.platform == "win32":
        CORE.define_macros.append(('EV_STANDALONE', '1'))
        return

    bdir = os.path.join(bext.build_temp, 'libev')
    ext.include_dirs.insert(0, bdir)

    if not os.path.isdir(bdir):
        os.makedirs(bdir)

    cwd = os.getcwd()
    os.chdir(bdir)
    try:
        if os.path.exists('config.h'):
            return
        rc = _system(libev_configure_command)
        if rc == 0 and sys.platform == 'darwin':
            make_universal_header('config.h', 'SIZEOF_LONG', 'SIZEOF_SIZE_T', 'SIZEOF_TIME_T')
    finally:
        os.chdir(cwd)


def configure_ares(bext, ext):
    bdir = os.path.join(bext.build_temp, 'c-ares')
    ext.include_dirs.insert(0, bdir)

    if not os.path.isdir(bdir):
        os.makedirs(bdir)

    if sys.platform == "win32":
        shutil.copy("c-ares\\ares_build.h.dist", os.path.join(bdir, "ares_build.h"))
        return

    cwd = os.getcwd()
    os.chdir(bdir)
    try:
        if os.path.exists('ares_config.h') and os.path.exists('ares_build.h'):
            return
        rc = _system(ares_configure_command)
        if rc == 0 and sys.platform == 'darwin':
            make_universal_header('ares_build.h', 'CARES_SIZEOF_LONG')
            make_universal_header('ares_config.h', 'SIZEOF_LONG', 'SIZEOF_SIZE_T', 'SIZEOF_TIME_T')
    finally:
        os.chdir(cwd)


if LIBEV_EMBED:
    CORE.define_macros += [('LIBEV_EMBED', '1'),
                           ('EV_COMMON', ''),  # we don't use void* data
                           # libev watchers that we don't use currently:
                           ('EV_CLEANUP_ENABLE', '0'),
                           ('EV_EMBED_ENABLE', '0'),
                           ("EV_PERIODIC_ENABLE", '0')]
    CORE.configure = configure_libev
    if sys.platform == "darwin":
        os.environ["CFLAGS"] = ("%s %s" % (os.environ.get("CFLAGS", ""), "-U__llvm__")).lstrip()
    if os.environ.get('GEVENTSETUP_EV_VERIFY') is not None:
        CORE.define_macros.append(('EV_VERIFY', os.environ['GEVENTSETUP_EV_VERIFY']))
else:
    CORE.libraries.append('ev')


if CARES_EMBED:
    ARES.sources += expand('c-ares/*.c')
    ARES.configure = configure_ares
    if sys.platform == 'win32':
        ARES.libraries += ['advapi32']
        ARES.define_macros += [('CARES_STATICLIB', '')]
    else:
        ARES.define_macros += [('HAVE_CONFIG_H', '')]
        if sys.platform != 'darwin':
            ARES.libraries += ['rt']
    ARES.define_macros += [('CARES_EMBED', '1')]
else:
    ARES.libraries.append('cares')
    ARES.define_macros += [('HAVE_NETDB_H', '')]


def make(done=[]):
    if not done:
        if os.path.exists('Makefile'):
            if "PYTHON" not in os.environ:
                os.environ["PYTHON"] = sys.executable
            system('make')
        done.append(1)


class sdist(_sdist):

    def run(self):
        renamed = False
        if os.path.exists('Makefile'):
            make()
            os.rename('Makefile', 'Makefile.ext')
            renamed = True
        try:
            return _sdist.run(self)
        finally:
            if renamed:
                os.rename('Makefile.ext', 'Makefile')


class my_build_ext(build_ext):

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
                raise BuildFailed
            else:
                raise
        if not PYPY:
            self.gevent_symlink(ext)
        return result

    def gevent_symlink(self, ext):
        # hack: create a symlink from build/../core.so to gevent/core.so
        # to prevent "ImportError: cannot import name core" failures
        try:
            fullname = self.get_ext_fullname(ext.name)
            modpath = fullname.split('.')
            filename = self.get_ext_filename(ext.name)
            filename = os.path.split(filename)[-1]
            if not self.inplace:
                filename = os.path.join(*modpath[:-1] + [filename])
                path_to_build_core_so = os.path.join(self.build_lib, filename)
                path_to_core_so = join('gevent', basename(path_to_build_core_so))
                link(path_to_build_core_so, path_to_core_so)
        except Exception:
            traceback.print_exc()


def link(source, dest):
    source = abspath(source)
    dest = abspath(dest)
    if source == dest:
        return
    try:
        os.unlink(dest)
    except OSError:
        pass
    try:
        os.symlink(source, dest)
        sys.stdout.write('Linking %s to %s\n' % (source, dest))
    except (OSError, AttributeError):
        sys.stdout.write('Copying %s to %s\n' % (source, dest))
        shutil.copyfile(source, dest)


class BuildFailed(Exception):
    pass


def read(name, *args):
    try:
        return open(join(dirname(__file__), name)).read(*args)
    except OSError:
        return ''


if PYPY:
    sys.path.insert(0, '.')
    # XXX ugly - need to find a better way
    system('cp -r libev gevent/libev')
    system('touch gevent/libev/__init__.py')
    system('cd gevent/libev && ./configure > configure_output.txt')
    from gevent import corecffi
    ext_modules = [corecffi.ffi.verifier.get_extension()]
    install_requires = []
    include_package_data = True
    run_make = False
else:
    ext_modules = [CORE,
                   ARES,
                   Extension(name="gevent._semaphore",
                             sources=["gevent/gevent._semaphore.c"]),
                   Extension(name="gevent._util",
                             sources=["gevent/gevent._util.c"])]
    install_requires = ['greenlet']
    include_package_data = False
    run_make = True


def run_setup(ext_modules, run_make):
    if run_make:
        make()
    setup(
        name='gevent',
        version=__version__,
        description='Coroutine-based network library',
        long_description=read('README.rst'),
        author='Denis Bilenko',
        author_email='denis.bilenko@gmail.com',
        url='http://www.gevent.org/',
        packages=['gevent'],
        include_package_data=include_package_data,
        ext_modules=ext_modules,
        cmdclass=dict(build_ext=my_build_ext, sdist=sdist),
        install_requires=install_requires,
        zip_safe=False,
        classifiers=[
            "License :: OSI Approved :: MIT License",
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
        run_setup(ext_modules, run_make=run_make)
    except BuildFailed:
        if ARES not in ext_modules:
            raise
        ext_modules.remove(ARES)
        run_setup(ext_modules, run_make=run_make)
    if ARES not in ext_modules:
        sys.stderr.write('\nWARNING: The gevent.ares extension has been disabled.\n')
