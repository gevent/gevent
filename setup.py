#!/usr/bin/env python
"""
gevent build & installation script
----------------------------------

If you have more than one libevent installed or it is installed in a
non-standard location, use the options to point to the right dirs:

    -Idir      add include dir
    -Ldir      add library dir
    --static   link libevent statically (default on win32)
    --dynamic  link libevent dynamically (default on any platform other than win32)

Also,

    setup.py build --libevent DIR

is a shortcut for

    setup.py build -IDIR -IDIR/include LDIR/.libs

"""

# XXX Options --static and --dynamic aren't tested for values other than theirs
#     defaults (that is, --static on win32, --dynamic on everything else)

import sys
import os
import re
import traceback
from distutils.core import Extension, setup
from os.path import join, isdir, abspath, basename

__version__ = re.search("__version__\s*=\s*'(.*)'", open('gevent/__init__.py').read(), re.M).group(1)
assert __version__


include_dirs = []                 # specified by -I
library_dirs = []                 # specified by -L
libevent_source_path = None       # specified by --libevent
VERBOSE = '-v' in sys.argv
static = sys.platform == 'win32'  # set to True with --static; set to False with --dynamic
extra_compile_args = []
sources = ['gevent/core.c']
libraries = []
extra_objects = []


# hack: create a symlink from build/../core.so to gevent/core.so to prevent "ImportError: cannot import name core" failures
cmdclass = {}
try:
    from distutils.command import build_ext
    class my_build_ext(build_ext.build_ext):
        def build_extension(self, ext):
            result = build_ext.build_ext.build_extension(self, ext)
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
                        print 'Linking %s to %s' % (path_to_build_core_so, path_to_core_so)
                        try:
                            os.unlink(path_to_core_so)
                        except OSError:
                            pass
                        if hasattr(os, 'symlink'):
                            os.symlink(path_to_build_core_so, path_to_core_so)
                        else:
                            import shutil
                            shutil.copyfile(path_to_build_core_so, path_to_core_so)
            except Exception:
                traceback.print_exc()
            return result
    cmdclass = {'build_ext': my_build_ext}
except Exception:
    traceback.print_exc()


def check_dir(path, must_exist):
    if not isdir(path):
        msg = 'Not a directory: %s' % path
        if must_exist:
            sys.exit(msg)


def add_include_dir(path, must_exist=True):
    if path not in include_dirs:
        check_dir(path, must_exist)
        include_dirs.append(path)


def add_library_dir(path, must_exist=True):
    if path not in library_dirs:
        check_dir(path, must_exist)
        library_dirs.append(path)


# parse options: -I NAME / -INAME / -L NAME / -LNAME / --libevent DIR / --static / --dynamic
# we're cutting out options from sys.path instead of using optparse
# so that these option can co-exists with distutils' options
i = 1
while i < len(sys.argv):
    arg = sys.argv[i]
    if arg == '-I':
        del sys.argv[i]
        add_include_dir(sys.argv[i])
    elif arg.startswith('-I'):
        add_include_dir(arg[2:])
    elif arg == '-L':
        del sys.argv[i]
        add_library_dir(sys.argv[i])
    elif arg.startswith('-L'):
        add_library_dir(arg[2:])
    elif arg == '--libevent':
        del sys.argv[i]
        libevent_source_path = sys.argv[i]
        add_include_dir(join(libevent_source_path, 'include'), must_exist=False)
        add_include_dir(libevent_source_path, must_exist=False)
        add_library_dir(join(libevent_source_path, '.libs'), must_exist=False)
        if sys.platform == 'win32':
            add_include_dir(join(libevent_source_path, 'compat'), must_exist=False)
            add_include_dir(join(libevent_source_path, 'WIN32-Code'), must_exist=False)
    elif arg == '--static':
        static = True
    elif arg == '--dynamic':
        static = False
    else:
        i = i+1
        continue
    del sys.argv[i]


if not sys.argv[1:] or '-h' in sys.argv or '--help' in ' '.join(sys.argv):
    print __doc__
else:
    if static:
        if not libevent_source_path:
            sys.exit('Please provide path to libevent source with --libevent DIR')
        extra_compile_args += ['-DHAVE_CONFIG_H']
        libevent_sources = ['event.c',
                            'buffer.c',
                            'evbuffer.c',
                            'event_tagging.c',
                            'evutil.c',
                            'log.c',
                            'signal.c',
                            'evdns.c',
                            'http.c',
                            'strlcpy.c']
        if sys.platform == 'win32':
            libraries = ['wsock32', 'advapi32']
            include_dirs.extend([ join(libevent_source_path, 'WIN32-Code'),
                                  join(libevent_source_path, 'compat') ])
            libevent_sources.append('WIN32-Code/win32.c')
            extra_compile_args += ['-DWIN32']
        else:
            libevent_sources += ['select.c']
            print 'XXX --static is not well supported on non-win32 platforms: only select is enabled'
        for filename in libevent_sources:
            sources.append( join(libevent_source_path, filename) )
    else:
        libraries = ['event']


gevent_core = Extension(name='gevent.core',
                        sources=sources,
                        include_dirs=include_dirs,
                        library_dirs=library_dirs,
                        libraries=libraries,
                        extra_objects=extra_objects,
                        extra_compile_args=extra_compile_args)


if __name__ == '__main__':
    setup(
        name='gevent',
        version=__version__,
        description='Python network library that uses greenlet and libevent for easy and scalable concurrency',
        author='Denis Bilenko',
        author_email='denis.bilenko@gmail.com',
        url='http://www.gevent.org/',
        packages=['gevent'],
        ext_modules=[gevent_core],
        cmdclass=cmdclass,
        classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Topic :: Internet",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Intended Audience :: Developers",
        "Development Status :: 4 - Beta"]
        )

