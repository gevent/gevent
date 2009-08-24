#!/usr/bin/env python
import sys
import os
import glob
import re
from distutils.core import Extension, setup


name = 'gevent.core'
sources = ['gevent/core.c']
ev_dir = None # override to skip searching for libevent


system_dirs = ['/usr/lib/libevent.*',
               '/usr/lib64/libevent.*',
               '/usr/local/lib/libevent.*',
               '/usr/local/lib64/libevent.*']


try:
    any
except NameError:
    def any(iterable):
        for i in iterable:
            if i:
                return True


if ev_dir is None and any(glob.glob(system_dir) for system_dir in system_dirs):
    print 'found system libevent for', sys.platform
    gevent_core = Extension(name=name,
                            sources=sources,
                            libraries=['event'])
elif ev_dir is None and glob.glob('%s/lib/libevent.*' % sys.prefix):
    print 'found installed libevent in', sys.prefix
    gevent_core = Extension(name=name,
                            sources=sources,
                            include_dirs=['%s/include' % sys.prefix],
                            library_dirs=['%s/lib' % sys.prefix],
                            libraries=['event'])
else:
    if ev_dir is None:
        l = glob.glob('../libevent*')
        l.reverse()
        for path in l:
            if os.path.isdir(path):
                ev_dir = path
                break
    if ev_dir:
        print 'found libevent build directory', ev_dir
        ev_incdirs = [ev_dir, ev_dir + '/compat']
        ev_extargs = []
        ev_extobjs = []
        ev_libraries = ['event']

        if sys.platform == 'win32':
            ev_incdirs.extend(['%s/WIN32-Code' % ev_dir,
                               '%s/compat' % ev_dir])
            sources.extend(['%s/%s' % (ev_dir, x) for x in [
                'WIN32-Code/misc.c', 'WIN32-Code/win32.c',
                'log.c', 'event.c']])
            ev_extargs = ['-DWIN32', '-DHAVE_CONFIG_H']
            ev_libraries = ['wsock32']
        else:
            ev_extobjs = glob.glob('%s/*.o' % dir)

        gevent_core = Extension(name=name,
                                sources=sources,
                                include_dirs=ev_incdirs,
                                extra_compile_args=ev_extargs,
                                extra_objects=ev_extobjs,
                                libraries=ev_libraries)
    else:
        sys.stderr.write("\nWARNING: couldn't find libevent installation or build directory: assuming system-wide libevent is installed.\n\n")
        gevent_core = Extension(name=name,
                                sources=sources,
                                libraries=['event'])

version = re.search("__version__\s*=\s*'(.*)'", open('gevent/__init__.py').read(), re.M).group(1).strip()
assert version, version

if __name__ == '__main__':
    setup(
        name='gevent',
        version=version,
        description='Python network library that uses greenlet and libevent for easy and scalable concurrency',
        author='Denis Bilenko',
        author_email='denis.bilenko@gmail.com',
        packages=['gevent'],
        ext_modules=[gevent_core],
        classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta"]
        )

