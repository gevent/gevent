#!/usr/bin/env python
"""gevent build & installation script"""
from __future__ import print_function
import sys
import os
import os.path
import sysconfig

# setuptools is *required* on Windows
# (https://bugs.python.org/issue23246) and for PyPy. No reason not to
# use it everywhere. v24.2.0 is needed for python_requires
from setuptools import Extension, setup
from setuptools import find_packages


from _setuputils import read
from _setuputils import read_version
from _setuputils import system
from _setuputils import PYPY, WIN
from _setuputils import IGNORE_CFFI
from _setuputils import SKIP_LIBUV
from _setuputils import ConfiguringBuildExt
from _setuputils import GeventClean
from _setuputils import BuildFailed
from _setuputils import cythonize1



if WIN:
    # Make sure the env vars that make.cmd needs are set
    if not os.environ.get('PYTHON_EXE'):
        os.environ['PYTHON_EXE'] = 'pypy' if PYPY else 'python'
    if not os.environ.get('PYEXE'):
        os.environ['PYEXE'] = os.environ['PYTHON_EXE']


if PYPY and sys.pypy_version_info[:3] < (2, 6, 1): # pylint:disable=no-member
    # We have to have CFFI >= 1.3.0, and this platform cannot upgrade
    # it.
    raise Exception("PyPy >= 2.6.1 is required")



__version__ = read_version()


from _setuplibev import libev_configure_command
from _setuplibev import LIBEV_EMBED
from _setuplibev import CORE

from _setupares import ARES

# Get access to the greenlet header file.
# The sysconfig dir is not enough if we're in a virtualenv
# See https://github.com/pypa/pip/issues/4610
include_dirs = [sysconfig.get_path("include")]
venv_include_dir = os.path.join(sys.prefix, 'include', 'site',
                                'python' + sysconfig.get_python_version())
venv_include_dir = os.path.abspath(venv_include_dir)
if os.path.exists(venv_include_dir):
    include_dirs.append(venv_include_dir)

# If we're installed via buildout, and buildout also installs
# greenlet, we have *NO* access to greenlet.h at all. So include
# our own copy as a fallback.
include_dirs.append('deps')

SEMAPHORE = Extension(name="gevent.__semaphore",
                      sources=["src/gevent/_semaphore.py"],
                      depends=['src/gevent/__semaphore.pxd'],
                      include_dirs=include_dirs)


LOCAL = Extension(name="gevent._local",
                  sources=["src/gevent/local.py"],
                  depends=['src/gevent/_local.pxd'],
                  include_dirs=include_dirs)


GREENLET = Extension(name="gevent._greenlet",
                     sources=[
                         "src/gevent/greenlet.py",
                     ],
                     depends=[
                         'src/gevent/_greenlet.pxd',
                         'src/gevent/__ident.pxd',
                         'src/gevent/_ident.py'
                     ],
                     include_dirs=include_dirs)

ABSTRACT_LINKABLE = Extension(name="gevent.__abstract_linkable",
                              sources=["src/gevent/_abstract_linkable.py"],
                              depends=['src/gevent/__abstract_linkable.pxd'],
                              include_dirs=include_dirs)


IDENT = Extension(name="gevent.__ident",
                  sources=["src/gevent/_ident.py"],
                  depends=['src/gevent/__ident.pxd'],
                  include_dirs=include_dirs)


IMAP = Extension(name="gevent.__imap",
                 sources=["src/gevent/_imap.py"],
                 depends=['src/gevent/__imap.pxd'],
                 include_dirs=include_dirs)

EVENT = Extension(name="gevent._event",
                  sources=["src/gevent/event.py"],
                  depends=['src/gevent/_event.pxd'],
                  include_dirs=include_dirs)

QUEUE = Extension(name="gevent._queue",
                  sources=["src/gevent/queue.py"],
                  depends=['src/gevent/_queue.pxd'],
                  include_dirs=include_dirs)

HUB_LOCAL = Extension(name="gevent.__hub_local",
                      sources=["src/gevent/_hub_local.py"],
                      depends=['src/gevent/__hub_local.pxd'],
                      include_dirs=include_dirs)

WAITER = Extension(name="gevent.__waiter",
                   sources=["src/gevent/_waiter.py"],
                   depends=['src/gevent/__waiter.pxd'],
                   include_dirs=include_dirs)

HUB_PRIMITIVES = Extension(name="gevent.__hub_primitives",
                           sources=["src/gevent/_hub_primitives.py"],
                           depends=['src/gevent/__hub_primitives.pxd'],
                           include_dirs=include_dirs)

GLT_PRIMITIVES = Extension(name="gevent.__greenlet_primitives",
                           sources=["src/gevent/_greenlet_primitives.py"],
                           depends=['src/gevent/__greenlet_primitives.pxd'],
                           include_dirs=include_dirs)

TRACER = Extension(name="gevent.__tracer",
                   sources=["src/gevent/_tracer.py"],
                   depends=['src/gevent/__tracer.pxd'],
                   include_dirs=include_dirs)


_to_cythonize = [
    GLT_PRIMITIVES,
    HUB_PRIMITIVES,
    HUB_LOCAL,
    WAITER,
    GREENLET,
    TRACER,

    ABSTRACT_LINKABLE,
    SEMAPHORE,
    LOCAL,

    IDENT,
    IMAP,
    EVENT,
    QUEUE,
]

EXT_MODULES = [
    CORE,
    ARES,
    ABSTRACT_LINKABLE,
    SEMAPHORE,
    LOCAL,
    GREENLET,
    IDENT,
    IMAP,
    EVENT,
    QUEUE,
    HUB_LOCAL,
    WAITER,
    HUB_PRIMITIVES,
    GLT_PRIMITIVES,
    TRACER,
]

LIBEV_CFFI_MODULE = 'src/gevent/libev/_corecffi_build.py:ffi'
LIBUV_CFFI_MODULE = 'src/gevent/libuv/_corecffi_build.py:ffi'
cffi_modules = []

if not WIN:
    # We can't properly handle (hah!) file-descriptors and
    # handle mapping on Windows/CFFI with libev, because the file needed,
    # libev_vfd.h, can't be included, linked, and used: it uses
    # Python API functions, and you're not supposed to do that from
    # CFFI code. Plus I could never get the libraries= line to ffi.compile()
    # correct to make linking work.
    # Also, we use the type `nlink_t`, which is not defined on Windows.
    cffi_modules.append(
        LIBEV_CFFI_MODULE
    )

if not SKIP_LIBUV:
    # libuv can't be built on manylinux1 because it needs glibc >= 2.12
    # but manylinux1 has only 2.5, so we set SKIP_LIBUV in the script make-manylinux
    cffi_modules.append(LIBUV_CFFI_MODULE)

greenlet_requires = [
    # We need to watch our greenlet version fairly carefully,
    # since we compile cython code that extends the greenlet object.
    # Binary compatibility would break if the greenlet struct changes.
    # (Which it did in 0.4.14 for Python 3.7)
    'greenlet >= 0.4.14; platform_python_implementation=="CPython"',
]

# Note that we don't add cffi to install_requires, it's
# optional. We tend to build and distribute wheels with the CFFI
# modules built and they can be imported if CFFI is installed.
# We need cffi 1.4.0 for new style callbacks;
# we need cffi 1.11.3 (on CPython 3) to avoid test errors.

# The exception is on Windows, where we want the libuv backend we distribute
# to be the default, and that requires cffi; but don't try to install it
# on PyPy or it messes up the build
cffi_requires = [
    "cffi >= 1.12.2 ; sys_platform == 'win32' and platform_python_implementation == 'CPython'",
]


install_requires = greenlet_requires + cffi_requires

# We use headers from greenlet, so it needs to be installed before we
# can compile. If it isn't already installed before we start
# installing, and we say 'pip install gevent', a 'setup_requires'
# doesn't save us: pip happily downloads greenlet and drops it in a
# .eggs/ directory in the build directory, but that directory doesn't
# have includes! So we fail to build a wheel, pip goes ahead and
# installs greenlet, and builds gevent again, which works.

# Since we ship the greenlet header for buildout support (which fails
# to install the headers at all, AFAICS, we don't need to bother with
# the buggy setup_requires.)

setup_requires = cffi_requires + []

if PYPY:
    # These use greenlet/greenlet.h, which doesn't exist on PyPy
    EXT_MODULES.remove(LOCAL)
    EXT_MODULES.remove(GREENLET)
    EXT_MODULES.remove(SEMAPHORE)
    EXT_MODULES.remove(ABSTRACT_LINKABLE)

    # As of PyPy 5.10, this builds, but won't import (missing _Py_ReprEnter)
    EXT_MODULES.remove(CORE)

    # This uses PyWeakReference and doesn't compile on PyPy
    EXT_MODULES.remove(IDENT)

    _to_cythonize.remove(LOCAL)
    _to_cythonize.remove(GREENLET)
    _to_cythonize.remove(SEMAPHORE)
    _to_cythonize.remove(IDENT)
    _to_cythonize.remove(ABSTRACT_LINKABLE)

    EXT_MODULES.remove(IMAP)
    _to_cythonize.remove(IMAP)

    EXT_MODULES.remove(EVENT)
    _to_cythonize.remove(EVENT)

    EXT_MODULES.remove(QUEUE)
    _to_cythonize.remove(QUEUE)

    EXT_MODULES.remove(HUB_LOCAL)
    _to_cythonize.remove(HUB_LOCAL)

    EXT_MODULES.remove(WAITER)
    _to_cythonize.remove(WAITER)

    EXT_MODULES.remove(GLT_PRIMITIVES)
    _to_cythonize.remove(GLT_PRIMITIVES)

    EXT_MODULES.remove(HUB_PRIMITIVES)
    _to_cythonize.remove(HUB_PRIMITIVES)

    EXT_MODULES.remove(TRACER)
    _to_cythonize.remove(TRACER)


for mod in _to_cythonize:
    EXT_MODULES.remove(mod)
    EXT_MODULES.append(cythonize1(mod))
del _to_cythonize


if IGNORE_CFFI and not PYPY:
    # Allow distributors to turn off CFFI builds
    # even if it's available, because CFFI always embeds
    # our copy of libev/libuv and they may not want that.
    del cffi_modules[:]

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

def make_long_description():
    readme = read('README.rst')
    about = read('doc', '_about.rst')
    install = read('doc', 'install.rst')
    readme = readme.replace('.. include:: doc/_about.rst',
                            about)
    readme = readme.replace('.. include:: doc/install.rst',
                            install)

    return readme


def run_setup(ext_modules, run_make):
    if run_make:
        if (not LIBEV_EMBED and not WIN and cffi_modules) or PYPY:
            # We're not embedding libev but we do want
            # to build the CFFI module. We need to configure libev
            # because the CORE Extension won't.
            # TODO: Generalize this.
            if LIBEV_CFFI_MODULE in cffi_modules and not WIN:
                system(libev_configure_command)
                # This changed to the libev directory, and ran configure .
                # It then copied the generated config.h back to the previous
                # directory, which happened to be beside us. In the embedded case,
                # we're building in a different directory, so it copied it back to build
                # directory, but here, we're building in the embedded directory, so
                # it gave us useless files.
                bad_file = None
                for bad_file in ('config.h', 'configure-output.txt'):
                    if os.path.exists(bad_file):
                        os.remove(bad_file)
                del bad_file

    setup(
        name='gevent',
        version=__version__,
        description='Coroutine-based network library',
        long_description=make_long_description(),
        license='MIT',
        keywords='greenlet coroutine cooperative multitasking light threads monkey',
        author='Denis Bilenko',
        author_email='denis.bilenko@gmail.com',
        maintainer='Jason Madden',
        maintainer_email='jason@nextthought.com',
        url='http://www.gevent.org/',
        project_urls={
            'Bug Tracker': 'https://github.com/gevent/gevent/issues',
            'Source Code': 'https://github.com/gevent/gevent/',
            'Documentation': 'http://www.gevent.org',
        },
        package_dir={'': 'src'},
        packages=find_packages('src'),
        include_package_data=True,
        ext_modules=ext_modules,
        cmdclass={
            'build_ext': ConfiguringBuildExt,
            'clean': GeventClean,
        },
        install_requires=install_requires,
        setup_requires=setup_requires,
        extras_require={
            'dnspython': [
                'dnspython >= 1.16.0',
                'idna',
            ],
            'events': [
                'zope.event',
                'zope.interface',
            ],
            'doc': [
                'repoze.sphinx.autointerface',
            ],
            'test': [
                # To the extent possible, we should work to make sure
                # our tests run, at least a basic set, without any of
                # these extra dependencies (i.e., skip things when they are
                # missing). This helps serve as a smoketest for users.
                'zope.interface',
                'zope.event',

                # Makes tests faster
                # Fails to build on PyPy on Windows.
                'psutil >= 5.6.1 ; platform_python_implementation == "CPython" or sys_platform != "win32"',
                # examples, called from tests, use this
                'requests',

                # We don't run coverage on Windows, and pypy can't build it there
                # anyway (coveralls -> cryptopgraphy -> openssl)
                'coverage>=5.0a4 ; sys_platform != "win32"',
                'coveralls>=1.7.0 ; sys_platform != "win32"',

                'futures ; python_version == "2.7"',
                'mock ; python_version == "2.7"',

                # leak checks. previously we had a hand-rolled version.
                'objgraph',
            ]
        },
        # It's always safe to pass the CFFI keyword, even if
        # cffi is not installed: it's just ignored in that case.
        cffi_modules=cffi_modules,
        zip_safe=False,
        test_suite="greentest.testrunner",
        classifiers=[
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3.4",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: Implementation :: CPython",
            "Programming Language :: Python :: Implementation :: PyPy",
            "Operating System :: MacOS :: MacOS X",
            "Operating System :: POSIX",
            "Operating System :: Microsoft :: Windows",
            "Topic :: Internet",
            "Topic :: Software Development :: Libraries :: Python Modules",
            "Intended Audience :: Developers",
            "Development Status :: 4 - Beta"
        ],
        python_requires=">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*",
        entry_points={
            'gevent.plugins.monkey.will_patch_all': [
                "signal_os_incompat = gevent.monkey:_subscribe_signal_os",
            ],
        },
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
    run_setup(EXT_MODULES, run_make=_BUILDING)
except BuildFailed:
    if ARES not in EXT_MODULES or not ARES.optional:
        raise
    EXT_MODULES.remove(ARES)
    run_setup(EXT_MODULES, run_make=_BUILDING)
if ARES not in EXT_MODULES and __name__ == '__main__' and _BUILDING:
    sys.stderr.write('\nWARNING: The gevent.ares extension has been disabled.\n')
