#!/usr/bin/env python
"""gevent build & installation script"""
from __future__ import print_function
import sys
import os

from _setuputils import read
from _setuputils import read_version
from _setuputils import system
from _setuputils import PYPY, WIN, CFFI_WIN_BUILD_ANYWAY
from _setuputils import ConfiguringBuildExt
from _setuputils import BuildFailed

# setuptools is *required* on Windows
# (https://bugs.python.org/issue23246) and for PyPy. No reason not to
# use it everywhere.
from setuptools import Extension, setup
from setuptools import find_packages

if PYPY and WIN and not CFFI_WIN_BUILD_ANYWAY:
    # We can't properly handle (hah!) file-descriptors and
    # handle mapping on Windows/CFFI, because the file needed,
    # libev_vfd.h, can't be included, linked, and used: it uses
    # Python API functions, and you're not supposed to do that from
    # CFFI code. Plus I could never get the libraries= line to ffi.compile()
    # correct to make linking work.
    raise Exception("Unable to install on PyPy/Windows")

if WIN:
    # Make sure the env vars that make.cmd needs are set
    if not os.environ.get('PYTHON_EXE'):
        os.environ['PYTHON_EXE'] = 'pypy' if PYPY else 'python'
    if not os.environ.get('PYEXE'):
        os.environ['PYEXE'] = os.environ['PYTHON_EXE']

if sys.version_info[:2] < (2, 7):
    raise Exception("Please install gevent 1.1 for Python 2.6")

from distutils.command.sdist import sdist as _sdist

__version__ = read_version()


from _setuplibev import libev_configure_command
from _setuplibev import LIBEV_EMBED
from _setuplibev import CORE

from _setupares import ARES


_ran_make = []


def make(targets=''):
    # NOTE: We have two copies of the makefile, one
    # for posix, one for windows. Our sdist command takes
    # care of renaming the posix one so it doesn't get into
    # the .tar.gz file (we don't want to re-run make in a released
    # file). We trigger off the presence/absence of that file altogether
    # to skip both posix and unix branches.
    # See https://github.com/gevent/gevent/issues/757
    if not _ran_make:
        if os.path.exists('Makefile'):
            if WIN:
                # make.cmd handles checking for PyPy and only making the
                # right things, so we can ignore the targets
                system("appveyor\\make.cmd")
            else:
                if "PYTHON" not in os.environ:
                    os.environ["PYTHON"] = sys.executable
                system('make ' + targets)
        _ran_make.append(1)


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



cffi_modules = ['src/gevent/libev/_corecffi_build.py:ffi']

if PYPY:
    install_requires = []
else:
    install_requires = ['greenlet >= 0.4.9']
    setup_kwds = {}

try:
    cffi = __import__('cffi')
except ImportError:
    setup_kwds = {}
else:
    _min_cffi_version = (1, 3, 0)
    _cffi_version_is_supported = cffi.__version_info__ >= _min_cffi_version
    _kwds = {'cffi_modules': cffi_modules}
    # We already checked for PyPy on Windows above and excluded it
    if PYPY:
        if not _cffi_version_is_supported:
            raise Exception("PyPy 2.6.1 or higher is required")
        setup_kwds = _kwds
    elif LIBEV_EMBED and (not WIN or CFFI_WIN_BUILD_ANYWAY):
        if not _cffi_version_is_supported:
            print("WARNING: CFFI version 1.3.0 is required to build CFFI backend", file=sys.stderr)
        else:
            # If we're on CPython, we can only reliably build
            # the CFFI module if we're embedding libev (in some cases
            # we wind up embedding it anyway, which may not be what the
            # distributor wanted).
            setup_kwds = _kwds

# If we are running info / help commands, or we're being imported by
# tools like pyroma, we don't need to build anything
_BUILDING = True
if ((len(sys.argv) >= 2
     and ('--help' in sys.argv[1:]
          or sys.argv[1] in ('--help-commands',
                             'egg_info',
                             '--version',
                             'clean',
                             '--long-description')))
    or __name__ != '__main__'):
    _BUILDING = False
    ext_modules = []
    include_package_data = PYPY # XXX look into this. we're excluding c files? Why? Old pypy builds? not needed anymore.
    run_make = False
elif PYPY:
    if not WIN:
        # We need to configure libev because the CORE Extension
        # won't do it (since we're not building it)
        system(libev_configure_command)

    # NOTE that we're NOT adding the distutils extension module, as
    # doing so compiles the module already: import gevent._corecffi_build
    # imports gevent, which imports the hub, which imports the core,
    # which compiles the module in-place. Instead we use the setup-time
    # support of cffi_modules
    ext_modules = [
        #_corecffi_build.ffi.distutils_extension(),
        ARES,
        # By building the semaphore with Cython under PyPy, we get
        # atomic operations (specifically, exiting/releasing), at the
        # cost of some speed (one trivial semaphore micro-benchmark put the pure-python version
        # at around 1s and the compiled version at around 4s). Some clever subclassing
        # and having only the bare minimum be in cython might help reduce that penalty.
        # NOTE: You must use version 0.23.4 or later to avoid a memory leak.
        # https://mail.python.org/pipermail/cython-devel/2015-October/004571.html
        # However, that's all for naught on up to and including PyPy 4.0.1 which
        # have some serious crashing bugs with GC interacting with cython,
        # so this is disabled (would need to add gevent/gevent._semaphore.c back to
        # the run_make line)
        #Extension(name="gevent._semaphore",
        #          sources=["gevent/gevent._semaphore.c"]),
    ]
    include_package_data = True
    run_make = 'src/gevent/gevent.ares.c'
else:
    ext_modules = [
        CORE,
        ARES,
        Extension(name="gevent._semaphore",
                  sources=["src/gevent/gevent._semaphore.c"]),
    ]
    include_package_data = False
    run_make = True

if run_make and os.path.exists("Makefile"):
    # The 'sdist' command renames our makefile after it
    # runs so we don't try to use it from a release tarball.

    # NOTE: This is effectively pointless and serves only for
    # documentation/metadata, because we run 'make' *before* we run
    # setup(), so installing cython happens too late.
    setup_requires = ['cython >= 0.24']
else:
    setup_requires = []


def run_setup(ext_modules, run_make):
    if run_make:
        if isinstance(run_make, str):
            make(run_make)
        else:
            make()
    setup(
        name='gevent',
        version=__version__,
        description='Coroutine-based network library',
        long_description=read('README.rst'),
        license='MIT',
        keywords='greenlet coroutine cooperative multitasking light threads monkey',
        author='Denis Bilenko',
        author_email='denis.bilenko@gmail.com',
        maintainer='Jason Madden',
        maintainer_email='jason@nextthought.com',
        url='http://www.gevent.org/',
        package_dir={'': 'src'},
        packages=find_packages('src'),
        include_package_data=include_package_data,
        ext_modules=ext_modules,
        cmdclass=dict(build_ext=ConfiguringBuildExt, sdist=sdist),
        install_requires=install_requires,
        setup_requires=setup_requires,
        zip_safe=False,
        test_suite="greentest.testrunner",
        classifiers=[
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3.3",
            "Programming Language :: Python :: 3.4",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: Implementation :: CPython",
            "Programming Language :: Python :: Implementation :: PyPy",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: POSIX",
            "Operating System :: Microsoft :: Windows",
            "Topic :: Internet",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Intended Audience :: Developers",
            "Development Status :: 4 - Beta"],
        **setup_kwds
    )

# Tools like pyroma expect the actual call to `setup` to be performed
# at the top-level at import time, so don't stash it away behind 'if
# __name__ == __main__'

if os.getenv('READTHEDOCS'):
    # Sometimes RTD fails to put our virtualenv bin directory
    # on the PATH, meaning we can't run cython. Fix that.
    new_path = os.environ['PATH'] + os.pathsep + os.path.dirname(sys.executable)
    os.environ['PATH'] = new_path

try:
    run_setup(ext_modules, run_make=run_make)
except BuildFailed:
    if ARES not in ext_modules:
        raise
    ext_modules.remove(ARES)
    run_setup(ext_modules, run_make=run_make)
if ARES not in ext_modules and __name__ == '__main__' and _BUILDING:
    sys.stderr.write('\nWARNING: The gevent.ares extension has been disabled.\n')
