#!/usr/bin/env python
"""gevent build & installation script"""
from __future__ import print_function
import sys
import os
import os.path


# setuptools is *required* on Windows
# (https://bugs.python.org/issue23246) and for PyPy. No reason not to
# use it everywhere. v24.2.0 is needed for python_requires
from setuptools import Extension, setup
from setuptools import find_packages


# -*- coding: utf-8 -*-
#
# We import other files that are siblings of this file as modules. In
# the past, setuptools guaranteed that this directory was on the path
# (typically, the working directory) but in a PEP517 world, that's no
# longer guaranteed to be the case. setuptools provides a PEP517
# backend (``setuptools.build_meta:__legacy__``) that *does* guarantee
# that, and we used it for a long time. But downstream packagers have begun
# complaining about using it. So we futz with the path ourself.
sys.path.insert(0, os.path.dirname(__file__))

from _setuputils import read
from _setuputils import read_version
from _setuputils import PYPY, WIN
from _setuputils import ConfiguringBuildExt
from _setuputils import GeventClean
from _setuputils import BuildFailed
from _setuputils import cythonize1
from _setuputils import get_include_dirs
from _setuputils import bool_from_environ

# Environment variables that are intended to be used outside of our own
# CI should be documented in ``installing_from_source.rst``

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


from _setuplibev import build_extension as build_libev_extension
from _setupares import ARES

CORE = cythonize1(build_libev_extension())

# Modules that we cythonize for performance.
# Be careful not to use simple names for these modules,
# as the non-static symbols cython generates do not include
# the module name. Thus an extension of 'gevent._queue'
# results in symbols like 'PyInit__queue', which is the same
# symbol used by the standard library _queue accelerator module.
# The name of the .pxd file must match the local name of the accelerator
# extension; however, sadly, the generated .c and .html files will
# still use the same name as the .py source.

SEMAPHORE = Extension(name="gevent._gevent_c_semaphore",
                      sources=["src/gevent/_semaphore.py"],
                      depends=['src/gevent/_gevent_c_semaphore.pxd'],
                      include_dirs=get_include_dirs())


LOCAL = Extension(name="gevent._gevent_clocal",
                  sources=["src/gevent/local.py"],
                  depends=['src/gevent/_gevent_clocal.pxd'],
                  include_dirs=get_include_dirs())


GREENLET = Extension(name="gevent._gevent_cgreenlet",
                     sources=[
                         "src/gevent/greenlet.py",
                     ],
                     depends=[
                         'src/gevent/_gevent_cgreenlet.pxd',
                         'src/gevent/_gevent_c_ident.pxd',
                         'src/gevent/_ident.py'
                     ],
                     include_dirs=get_include_dirs())

ABSTRACT_LINKABLE = Extension(name="gevent._gevent_c_abstract_linkable",
                              sources=["src/gevent/_abstract_linkable.py"],
                              depends=['src/gevent/_gevent_c_abstract_linkable.pxd'],
                              include_dirs=get_include_dirs())


IDENT = Extension(name="gevent._gevent_c_ident",
                  sources=["src/gevent/_ident.py"],
                  depends=['src/gevent/_gevent_c_ident.pxd'],
                  include_dirs=get_include_dirs())


IMAP = Extension(name="gevent._gevent_c_imap",
                 sources=["src/gevent/_imap.py"],
                 depends=['src/gevent/_gevent_c_imap.pxd'],
                 include_dirs=get_include_dirs())

EVENT = Extension(name="gevent._gevent_cevent",
                  sources=["src/gevent/event.py"],
                  depends=['src/gevent/_gevent_cevent.pxd'],
                  include_dirs=get_include_dirs())

QUEUE = Extension(name="gevent._gevent_cqueue",
                  sources=["src/gevent/queue.py"],
                  depends=['src/gevent/_gevent_cqueue.pxd'],
                  include_dirs=get_include_dirs())

HUB_LOCAL = Extension(name="gevent._gevent_c_hub_local",
                      sources=["src/gevent/_hub_local.py"],
                      depends=['src/gevent/_gevent_c_hub_local.pxd'],
                      include_dirs=get_include_dirs())

WAITER = Extension(name="gevent._gevent_c_waiter",
                   sources=["src/gevent/_waiter.py"],
                   depends=['src/gevent/_gevent_c_waiter.pxd'],
                   include_dirs=get_include_dirs())

HUB_PRIMITIVES = Extension(name="gevent._gevent_c_hub_primitives",
                           sources=["src/gevent/_hub_primitives.py"],
                           depends=['src/gevent/_gevent_c_hub_primitives.pxd'],
                           include_dirs=get_include_dirs())

GLT_PRIMITIVES = Extension(name="gevent._gevent_c_greenlet_primitives",
                           sources=["src/gevent/_greenlet_primitives.py"],
                           depends=['src/gevent/_gevent_c_greenlet_primitives.pxd'],
                           include_dirs=get_include_dirs())

TRACER = Extension(name="gevent._gevent_c_tracer",
                   sources=["src/gevent/_tracer.py"],
                   depends=['src/gevent/_gevent_c_tracer.pxd'],
                   include_dirs=get_include_dirs())


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

if bool_from_environ('GEVENTSETUP_DISABLE_ARES'):
    print("c-ares module disabled, not building")
    EXT_MODULES.remove(ARES)

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

cffi_modules.append(LIBUV_CFFI_MODULE)

greenlet_requires = [
    # We need to watch our greenlet version fairly carefully,
    # since we compile cython code that extends the greenlet object.
    # Binary compatibility would break if the greenlet struct changes.
    # (Which it did in 0.4.14 for Python 3.7 and again in 0.4.17; with
    # the release of 1.0a1 it began promising ABI stability with SemVer
    # so we can add an upper bound).
    # 1.1.0 is required for 3.10; it has a new ABI, but only on 1.1.0.
    # 1.1.3 is needed for 3.11, and supports everything 1.1.0 did.
    'greenlet >= 1.1.3, < 2.0; platform_python_implementation=="CPython"',
]

# Note that we don't add cffi to install_requires, it's
# optional. We tend to build and distribute wheels with the CFFI
# modules built and they can be imported if CFFI is installed.
# We need cffi 1.4.0 for new style callbacks;
# we need cffi 1.11.3 (on CPython 3) to avoid test errors.

# The exception is on Windows, where we want the libuv backend we distribute
# to be the default, and that requires cffi; but don't try to install it
# on PyPy or it messes up the build
CFFI_DEP = "cffi >= 1.12.2 ; platform_python_implementation == 'CPython'"
CFFI_REQUIRES = [
    CFFI_DEP + " and sys_platform == 'win32'"
]


install_requires = greenlet_requires + CFFI_REQUIRES + [
    # For event notification.
    'zope.event',
    # For event definitions, and our own interfaces; those should
    # ultimately be published, but at this writing only the event
    # interfaces are.
    'zope.interface',
    # setuptools is also used (via pkg_resources) for event
    # notifications. It's a hard dependency of zope.interface
    # anyway.
    'setuptools',
]

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

setup_requires = CFFI_REQUIRES + []

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


## Extras

EXTRA_DNSPYTHON = [
    # We're not currently compatible with 2.0, and dnspython 1.x isn't
    # compatible weth Python 3.10 because of the removal of ``collections.MutableMapping``.
    'dnspython >= 1.16.0, < 2.0; python_version < "3.10"',
    'idna; python_version < "3.10"',
]
EXTRA_EVENTS = [
    # No longer does anything, but the extra must stay around
    # to avoid breaking install scripts.
    # Remove this in 2021.
]

EXTRA_PSUTIL_DEPS = [
    # Versions of PyPy2 prior to 7.3.1 (maybe?) are incompatible with
    # psutil >= 5.6.4. 5.7.0 seems to work.
    # https://github.com/giampaolo/psutil/issues/1659
    # PyPy on Windows can't build psutil, it fails to link with the missing symbol
    # PyErr_SetFromWindowsErr.
    'psutil >= 5.7.0; sys_platform != "win32" or platform_python_implementation == "CPython"',
]

EXTRA_MONITOR = [
] + EXTRA_PSUTIL_DEPS

EXTRA_RECOMMENDED = [
    # We need this at runtime to use the libev-CFFI and libuv backends
    CFFI_DEP,
    # Backport of selectors module to Python 2
    'selectors2 ; python_version == "2.7"',
    # Backport of socket.socketpair to Python 2; only needed on Windows
    'backports.socketpair ; python_version == "2.7" and sys_platform == "win32"',
] + EXTRA_DNSPYTHON + EXTRA_EVENTS + EXTRA_MONITOR


def make_long_description():
    readme = read('README.rst')
    about = read('docs', '_about.rst')
    install = read('docs', 'install.rst')
    readme = readme.replace('.. include:: docs/_about.rst',
                            about)
    readme = readme.replace('.. include:: docs/install.rst',
                            install)

    return readme


def run_setup(ext_modules):
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
        # Using ``include_package_data`` causes our generated ``.c``
        # and ``.h`` files to be included in the installation. Those
        # aren't needed at runtime (the ``.html`` files generated by
        # Cython's annotation are much nicer to browse anyway, but we
        # don't want to include those either), and downstream
        # distributors have complained about them, so we don't want to
        # include them. Nor do we want to include ``.pyx`` or ``.pxd``
        # files that aren't considered public; the only ``.pxd`` files
        # that ever offered the required Cython annotations to produce
        # stable APIs weere in the libev cext backend; all of the
        # internal optimizations provided by Cython compiling existing
        # ``.py`` files using a matching ``.pxd`` do not. Furthermore,
        # there are ABI issues that make distributing those extremely
        # fragile. So do not use ``include_package_data``, explicitly
        # spell out what we need. See https://github.com/gevent/gevent/issues/1568.
        package_data={
            # For any package
            '': [
                # Include files needed to run tests
                '*.pem',
                '*.crt',
                '*.txt',
                '*.key',
                # We have a few .py files that aren't technically in packages;
                # This one enables coverage for testing.
                'coveragesite/*.py',
            ]
        },
        ext_modules=ext_modules,
        cmdclass={
            'build_ext': ConfiguringBuildExt,
            'clean': GeventClean,
        },
        install_requires=install_requires,
        setup_requires=setup_requires,
        extras_require={
            # Each extra intended for end users must be documented in install.rst
            'dnspython': EXTRA_DNSPYTHON,
            'events': EXTRA_EVENTS,
            'monitor': EXTRA_MONITOR,
            'recommended': EXTRA_RECOMMENDED,
            # End end-user extras
            'docs': [
                'repoze.sphinx.autointerface',
                'sphinxcontrib-programoutput',
                'zope.schema',
            ],
            # To the extent possible, we should work to make sure
            # our tests run, at least a basic set, without any of
            # these extra dependencies (i.e., skip things when they are
            # missing). This helps serve as a smoketest for users.
            'test': EXTRA_RECOMMENDED + [
                # examples, called from tests, use this
                'requests',

                # We don't run coverage on Windows, and pypy can't build it there
                # anyway (coveralls -> cryptopgraphy -> openssl).
                # coverage 5 needs coveralls 1.11
                'coverage >= 5.0 ; sys_platform != "win32"',
                'coveralls>=1.7.0 ; sys_platform != "win32"',

                'futures ; python_version == "2.7"',
                'mock ; python_version == "2.7"',

                # leak checks. previously we had a hand-rolled version.
                'objgraph',

                # The backport for contextvars to test patching. It sadly uses the same
                # import name as the stdlib module.
                'contextvars == 2.4 ; python_version > "3.0" and python_version < "3.7"',
            ],
        },
        # It's always safe to pass the CFFI keyword, even if
        # cffi is not installed: it's just ignored in that case.
        cffi_modules=cffi_modules,
        zip_safe=False,
        test_suite="greentest.testrunner",
        classifiers=[
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
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
        python_requires=">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5",
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
    run_setup(EXT_MODULES)
except BuildFailed:
    if ARES not in EXT_MODULES or not ARES.optional:
        raise
    sys.stderr.write('\nWARNING: The gevent.ares extension has been disabled.\n')
    EXT_MODULES.remove(ARES)
    run_setup(EXT_MODULES)
