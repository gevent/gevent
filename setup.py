#!/usr/bin/env python
"""
gevent build & installation script
----------------------------------

If you have more than one libevent installed or it is installed in a
non-standard location, use the options to point to the right dirs:

    -Idir   add include dir
    -Ldir   add library dir
    -1      prefer libevent1
    -2      prefer libevent2

Also,

    setup.py build --libevent DIR

is a shortcut for

    setup.py build -IDIR -IDIR/include LDIR/.libs

"""
import sys
import os
import re
from distutils.core import Extension, setup
from os.path import join, exists, isdir
try:
    import ctypes
except ImportError:
    ctypes = None


__version__ = re.search("__version__\s*=\s*'(.*)'", open('gevent/__init__.py').read(), re.M).group(1).strip()
assert __version__

include_dirs = []
library_dirs = []
extra_compile_args = []
LIBEVENT_MAJOR = None # 1 or 2
VERBOSE = '-v' in sys.argv

libevent_fn = 'libevent.so'
if sys.platform == 'darwin':
    libevent_fn = 'libevent.dylib'

def check_dir(path, must_exist):
    if not isdir(path):
        msg = 'Not a directory: %s' % path
        if must_exist:
            sys.exit(msg)

def add_include_dir(path, must_exist=True):
    check_dir(path, must_exist)
    include_dirs.append(path)

def add_library_dir(path, must_exist=True):
    check_dir(path, must_exist)
    library_dirs.append(path)

def get_version_from_include_path(d):
    if VERBOSE:
        print 'checking %s for event2/event.h (libevent 2) and event.h (libevent 1)' % d
    event_h = join(d, 'event2', 'event.h')
    if exists(event_h):
        print 'Using libevent 2: %s' % event_h
        return 2
    event_h = join(d, 'event.h')
    if exists(event_h):
        print 'Using libevent 1: %s' % event_h
        return 1

def get_version_from_ctypes(cdll, path):
    try:
        get_version = cdll.event_get_version
        get_version.restype = ctypes.c_char_p
    except AttributeError:
        pass
    else:
        version = get_version()
        print 'Using libevent %s: %s' % (version, path)
        if version.startswith('1'):
            return 1
        elif version.startswith('2'):
            return 2
        else:
            print 'Wierd response from %s get_version(): %r' % (path, version)

def get_version_from_path(path):
    v1 = re.search('[^\d]1\.', path)
    v2 = re.search('[^\d]2\.', path)
    if v1 is not None:
        if v2 is None:
            print 'Using libevent 1: "%s"' % path
            return 1
    elif v2 is not None:
        print 'Using libevent 2: "%s"' % path
        return 2

def get_version_from_library_path(d):
    if VERBOSE:
        print 'checking %s for %s' % (d, libevent_fn)
    libevent_fpath = join(d, libevent_fn)
    if exists(libevent_fpath):
        if ctypes:
            return get_version_from_ctypes( ctypes.CDLL(libevent_fpath), libevent_fpath )
        else:
            return get_version_from_path(d)

def unique(lst):
    result = []
    for item in lst:
        if item not in result:
            result.append(item)
    return result


# parse options: -I name / -Iname / -L name / -Lname / -1 / -2
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
    elif arg == '-1':
        LIBEVENT_MAJOR = 1
    elif arg == '-2':
        LIBEVENT_MAJOR = 2
    elif arg == '--libevent':
        del sys.argv[i]
        libevent_source_path = sys.argv[i]
        add_include_dir(join(libevent_source_path, 'include'), must_exist=False)
        add_include_dir(libevent_source_path, must_exist=False)
        add_library_dir(join(libevent_source_path, '.libs'), must_exist=False)
    else:
        i = i+1
        continue
    del sys.argv[i]


if not sys.argv[1:] or '-h' in sys.argv or '--help' in sys.argv:
    print __doc__
else:
    # try to figure out libevent version from -I and -L options
    for d in include_dirs:
        if LIBEVENT_MAJOR is not None:
            break
        LIBEVENT_MAJOR = get_version_from_include_path(d)

    for d in library_dirs:
        if LIBEVENT_MAJOR is not None:
            break
        LIBEVENT_MAJOR = get_version_from_library_path(d)

    if LIBEVENT_MAJOR is None and ctypes:
        libevent = ctypes.cdll.LoadLibrary(libevent_fn)
        LIBEVENT_MAJOR = get_version_from_ctypes(libevent, libevent_fn)

    # search system library dirs (unless explicit library directory was provided)
    if LIBEVENT_MAJOR is None and not library_dirs:
        library_paths = os.environ.get('LD_LIBRARY_PATH', '').split(':')
        library_paths += ['%s/lib' % sys.prefix,
                          '%s/lib64' % sys.prefix,
                          '/usr/lib/',
                          '/usr/lib64/',
                          '/usr/local/lib/',
                          '/usr/local/lib64/']

        for x in unique(library_paths):
            LIBEVENT_MAJOR = get_version_from_library_path(x)
            if LIBEVENT_MAJOR is not None:
                add_library_dir(x)
                break

    if LIBEVENT_MAJOR is None:
        print 'Cannot guess the version of libevent installed on your system. DEFAULTING TO 1.'
        LIBEVENT_MAJOR = 1
    
    extra_compile_args.append( '-DUSE_LIBEVENT_%s' % LIBEVENT_MAJOR )


gevent_core = Extension(name = 'gevent.core',
                        sources=['gevent/core.c'],
                        include_dirs=include_dirs,
                        library_dirs=library_dirs,
                        libraries=['event'],
                        extra_compile_args=extra_compile_args)


if __name__ == '__main__':
    setup(
        name='gevent',
        version=__version__,
        description='Python network library that uses greenlet and libevent for easy and scalable concurrency',
        author='Denis Bilenko',
        author_email='denis.bilenko@gmail.com',
        url='http://gevent.org/',
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

