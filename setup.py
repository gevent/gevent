#!/usr/bin/env python
"""
gevent build & installation script
----------------------------------

If you have more than one libevent installed or it is installed in a
non-standard location, use the options to point to the right dirs:

    -IPATH            add include PATH
    -LPATH            add library PATH
   --libevent PATH    use libevent from PATH
       If configure and make have been run in PATH, this implies
      -IPATH -IPATH/include -LPATH/.libs
      Otherwise setup.py will run configure and make and link
      statically with libevent.
"""

import sys
import os
import re
import traceback
import glob
from os.path import join, isdir, abspath, basename, exists, dirname

try:
    from setuptools import Extension, setup
except ImportError:
    from distutils.core import Extension, setup
from distutils.command import build_ext

__version__ = re.search("__version__\s*=\s*'(.*)'", open('gevent/__init__.py').read(), re.M).group(1)
assert __version__


include_dirs = []                 # specified by -I
library_dirs = []                 # specified by -L
libevent_source_path = None       # specified by --libevent
extra_compile_args = []
sources = ['gevent/core.c']
libraries = []


def run_cython(cython_command='cython'):
    sources = glob.glob('gevent/*.pyx') + glob.glob('gevent/*.pxi')
    if not sources:
        if not os.path.exists('gevent/core.c'):
            print >> sys.stderr, 'Could not find gevent/core.c'
    if os.path.exists('gevent/core.c'):
        core_c_mtime = os.stat('gevent/core.c').st_mtime
        changed = [filename for filename in sources if (os.stat(filename).st_mtime - core_c_mtime) > 1]
        if not changed:
            return
        print >> sys.stderr, 'Running %s (changed: %s)' % (cython_command, ', '.join(changed))
    else:
        print >> sys.stderr, 'Running %s' % cython_command
    cython_result = os.system('%s gevent/core.pyx' % cython_command)
    if cython_result:
        if os.system('%s -V 2> %s' % (cython_command, os.devnull)):
            # there's no cython in the system
            print >> sys.stderr, 'No cython found, cannot rebuild core.c'
            return
        sys.exit(1)


class my_build_ext(build_ext.build_ext):
    user_options = (build_ext.build_ext.user_options
                    + [("cython=", None, "path to the cython executable")])

    def initialize_options(self):
        build_ext.build_ext.initialize_options(self)
        self.cython = "cython"

    def build_extension(self, ext):
        compile_libevent(self)
        if self.cython:
            run_cython(self.cython)
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
                        print 'Linking %s to %s' % (path_to_build_core_so, path_to_core_so)
                        os.symlink(path_to_build_core_so, path_to_core_so)
                    else:
                        print 'Copying %s to %s' % (path_to_build_core_so, path_to_core_so)
                        import shutil
                        shutil.copyfile(path_to_build_core_so, path_to_core_so)
        except Exception:
            traceback.print_exc()
        return result


def mysystem(cmd):
    err = os.system(cmd)
    if err:
        sys.exit("running %r failed" % cmd)


def compile_libevent(build):
    sdir = libevent_source_path
    if not sdir:
        return

    from distutils import sysconfig

    configure = os.path.abspath(os.path.join(sdir, "configure"))
    addlibs = []
    bdir = os.path.join(build.build_temp, "libevent")
    if not os.path.isdir(bdir):
        os.makedirs(bdir)

    cwd = os.getcwd()
    os.chdir(bdir)
    try:
        if "CC" not in os.environ:
            cc = sysconfig.get_config_var("CC")
            if cc:
                os.environ["CC"] = cc

            archflags = sysconfig.get_config_var("ARCHFLAGS")
            if archflags:
                os.environ["AM_CFLAGS"] = archflags

        if not exists("./config.status"):
            mysystem("%s --with-pic --disable-shared --disable-dependency-tracking" % configure)
        if "bsd" in sys.platform:
            mysystem("gmake")
        else:
            mysystem("make")

        for line in open("Makefile"):
            if line.startswith("LIBS = "):
                addlibs = [x[2:] for x in line[len("LIBS = "):].strip().split() if x.startswith("-l")]
    finally:
        os.chdir(cwd)

    if build is None:
        return

    if build.include_dirs is None:
        build.include_dirs = []
    if build.library_dirs is None:
        build.library_dirs = []
    # bdir is needed for event-config.h
    build.include_dirs[:0] = [bdir, "%s/include" % bdir, sdir, "%s/include" % sdir]
    build.library_dirs[:0] = ["%s/.libs" % bdir]
    build.libraries.extend(addlibs)

    cc = build.compiler
    if sys.platform == "darwin":
        # stupid apple: http://developer.apple.com/mac/library/qa/qa2006/qa1393.html
        cc.linker_so += ['-Wl,-search_paths_first']
        cc.linker_exe += ['-Wl,-search_paths_first']

    cc.set_include_dirs(build.include_dirs)
    cc.set_library_dirs(build.library_dirs)
    cc.set_libraries(build.libraries)


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


def enable_libevent_source_path():
    add_include_dir(join(libevent_source_path, 'include'), must_exist=False)
    add_include_dir(libevent_source_path, must_exist=False)
    add_library_dir(join(libevent_source_path, '.libs'), must_exist=False)
    if sys.platform == 'win32':
        add_include_dir(join(libevent_source_path, 'compat'), must_exist=False)
        add_include_dir(join(libevent_source_path, 'WIN32-Code'), must_exist=False)

    global compile_libevent
    compile_libevent = lambda *a: None


# parse options: -I NAME / -INAME / -L NAME / -LNAME / --libevent DIR
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
    else:
        i += 1
        continue
    del sys.argv[i]

if libevent_source_path is None and os.path.isdir("libevent-src"):
    libevent_source_path = "libevent-src"
    print "using libevent sources in libevent-src"

# sources used when building on windows; this includes sources of both libevent-1.4
# and libevent-2 combined, but will filter out the files that do not exist
libevent_sources = '''buffer.c
bufferevent_async.c
bufferevent.c
bufferevent_filter.c
bufferevent_pair.c
bufferevent_ratelim.c
bufferevent_sock.c
buffer_iocp.c
evbuffer.c
evdns.c
event.c
event_iocp.c
event_tagging.c
evmap.c
evrpc.c
evthread.c
evthread_win32.c
evutil.c
evutil_rand.c
http.c
listener.c
log.c
signal.c
strlcpy.c
WIN32-Code/win32.c
win32select.c'''.split()


if not sys.argv[1:] or '-h' in sys.argv or '--help' in ' '.join(sys.argv):
    print __doc__
else:
    if sys.platform == 'win32':
        if not libevent_source_path:
            sys.exit('Please provide path to libevent source with --libevent DIR')
        enable_libevent_source_path()
        extra_compile_args += ['-DHAVE_CONFIG_H', '-DWIN32']
        libraries = ['wsock32', 'advapi32', 'ws2_32', 'shell32']
        include_dirs.extend([join(libevent_source_path, 'WIN32-Code'),
                             join(libevent_source_path, 'compat')])
        libevent_sources = [join(libevent_source_path, filename) for filename in libevent_sources]
        libevent_sources = [filename for filename in libevent_sources if exists(filename)]
        if not libevent_sources:
            sys.exit('No libevent sources found in %s' % libevent_source_path)
        for filename in libevent_sources:
            sources.append(filename)
    else:
        libraries = ['event']
        if (libevent_source_path
            and (exists(join(libevent_source_path, ".libs"))
                 or not exists(join(libevent_source_path, "configure")))):
            enable_libevent_source_path()

gevent_core = Extension(name='gevent.core',
                        sources=sources,
                        include_dirs=include_dirs,
                        library_dirs=library_dirs,
                        libraries=libraries,
                        extra_compile_args=extra_compile_args)


def read(name):
    return open(join(dirname(__file__), name)).read()


if __name__ == '__main__':
    if sys.argv[1:] == ['cython']:
        run_cython()
    else:
        setup(
            name='gevent',
            version=__version__,
            description='Python network library that uses greenlet and libevent for easy and scalable concurrency',
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
