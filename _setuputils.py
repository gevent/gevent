# -*- coding: utf-8 -*-
"""
gevent build utilities.
"""

from __future__ import print_function, absolute_import, division

import re
import os
import os.path
import sys
import sysconfig
from distutils import sysconfig as dist_sysconfig
from subprocess import check_call
from glob import glob

from setuptools import Extension as _Extension
from setuptools.command.build_ext import build_ext

THIS_DIR = os.path.dirname(__file__)

## Exported configurations

PYPY = hasattr(sys, 'pypy_version_info')
WIN = sys.platform.startswith('win')
PY311 = sys.version_info[:2] >= (3, 11)
PY312 = sys.version_info[:2] >= (3, 12)


RUNNING_ON_TRAVIS = os.environ.get('TRAVIS')
RUNNING_ON_APPVEYOR = os.environ.get('APPVEYOR')
RUNNING_ON_GITHUB_ACTIONS = os.environ.get('GITHUB_ACTIONS')
RUNNING_ON_CI = RUNNING_ON_TRAVIS or RUNNING_ON_APPVEYOR or RUNNING_ON_GITHUB_ACTIONS
RUNNING_FROM_CHECKOUT = os.path.isdir(os.path.join(THIS_DIR, ".git"))


LIBRARIES = []
DEFINE_MACROS = []


if WIN:
    LIBRARIES += ['ws2_32']
    DEFINE_MACROS += [('FD_SETSIZE', '1024'), ('_WIN32', '1')]

### File handling

def quoted_abspath(*segments):
    return '"' + os.path.abspath(os.path.join(*segments)) + '"'

def read(*names):
    """Read a file path relative to this file."""
    with open(os.path.join(THIS_DIR, *names)) as f:
        return f.read()

def read_version(name="src/gevent/__init__.py"):
    contents = read(name)
    version = re.search(r"__version__\s*=\s*'(.*)'", contents, re.M).group(1)
    assert version, "could not read version"
    return version

def dep_abspath(depname, *extra):
    return os.path.abspath(os.path.join('deps', depname, *extra))

def quoted_dep_abspath(depname):
    return quoted_abspath(dep_abspath(depname))

def glob_many(*globs):
    """
    Return a list of all the glob patterns expanded.
    """
    result = []
    for pattern in globs:
        result.extend(glob(pattern))
    return sorted(result)


## Configuration

# Environment variables that are intended to be used outside of our own
# CI should be documented in ``installing_from_source.rst``.
# They should all begin with ``GEVENTSETUP_``


def bool_from_environ(key):
    value = os.environ.get(key)
    if not value:
        return
    value = value.lower().strip()
    if value in ('1', 'true', 'on', 'yes'):
        return True
    if value in ('0', 'false', 'off', 'no'):
        return False
    raise ValueError('Environment variable %r has invalid value %r. '
                     'Please set it to 1, 0 or an empty string' % (key, value))


def _check_embed(key, defkey, path=None, warn=False):
    """
    Find a boolean value, configured in the environment at *key* or
    *defkey* (typically, *defkey* will be shared by several calls). If
    those don't exist, then check for the existence of *path* and return
    that (if path is given)
    """
    value = bool_from_environ(key)
    if value is None:
        value = bool_from_environ(defkey)
    if value is not None:
        if warn:
            print("Warning: gevent setup: legacy environment key %s or %s found"
                  % (key, defkey))
        return value
    return os.path.exists(path) if path is not None else None

def should_embed(dep_name):
    """
    Check the configuration for the dep_name and see if it should be
    embedded. Environment keys are derived from the dep name: libev
    becomes GEVENTSETUP_EMBED_LIBEV and c-ares becomes
    GEVENTSETUP_EMBED_CARES.
    """
    path = dep_abspath(dep_name)
    normal_dep_key = dep_name.replace('-', '').upper()

    default_key = 'GEVENTSETUP_EMBED'
    dep_key = default_key + '_' + normal_dep_key

    result = _check_embed(dep_key, default_key)
    if result is not None:
        return result

    # Not defined, check legacy settings, and fallback to the path

    legacy_default_key = 'EMBED'
    legacy_dep_key = normal_dep_key + '_' + legacy_default_key


    return _check_embed(legacy_dep_key, legacy_default_key, path,
                        warn=True)

## Headers

def get_include_dirs(*extra_paths):
    """
    Return additional include directories that might be needed to
    compile extensions. Specifically, we need the greenlet.h header
    in many of our extensions.
    """
    # setuptools will put the normal include directory for Python.h on the
    # include path automatically. We don't want to override that with
    # a different Python.h if we can avoid it: On older versions of Python,
    # that can cause issues with debug builds (see https://github.com/gevent/gevent/issues/1461)
    # so order matters here.
    #
    # sysconfig.get_path('include') will return the path to the main include
    # directory. In a virtual environment, that's a symlink to the main
    # Python installation include directory:
    #   sysconfig.get_path('include') -> /path/to/venv/include/python3.8
    #   /path/to/venv/include/python3.7 -> /pythondir/include/python3.8
    #
    # distutils.sysconfig.get_python_inc() returns the main Python installation
    # include directory:
    #   distutils.sysconfig.get_python_inc() -> /pythondir/include/python3.8
    #
    # Neither sysconfig dir is not enough if we're in a virtualenv; the greenlet.h
    # header goes into a site/ subdir. See https://github.com/pypa/pip/issues/4610
    dist_inc_dir = os.path.abspath(dist_sysconfig.get_python_inc()) # 1
    sys_inc_dir = os.path.abspath(sysconfig.get_path("include")) # 2
    venv_include_dir = os.path.join(
        sys.prefix, 'include', 'site',
        'python' + sysconfig.get_python_version()
    )
    venv_include_dir = os.path.abspath(venv_include_dir)

    # If we're installed via buildout, and buildout also installs
    # greenlet, we have *NO* access to greenlet.h at all. So include
    # our own copy as a fallback.
    dep_inc_dir = os.path.abspath('deps') # 3

    return [
        p
        for p in (dist_inc_dir, sys_inc_dir, dep_inc_dir) + extra_paths
        if os.path.exists(p)
    ]


## Processes

def _system(cmd, cwd=None, env=None, **kwargs):
    sys.stdout.write('Running %r in %s\n' % (cmd, cwd or os.getcwd()))
    sys.stdout.flush()
    if 'shell' not in kwargs:
        kwargs['shell'] = True
    env = env or os.environ.copy()
    return check_call(cmd, cwd=cwd, env=env, **kwargs)


def system(cmd, cwd=None, env=None, **kwargs):
    if _system(cmd, cwd=cwd, env=env, **kwargs):
        sys.exit(1)


###
# Cython
###

COMMON_UTILITY_INCLUDE_DIR = "src/gevent/_generated_include"

# Based on code from
# http://cython.readthedocs.io/en/latest/src/reference/compilation.html#distributing-cython-modules
def _dummy_cythonize(extensions, **_kwargs):
    for extension in extensions:
        sources = []
        for sfile in extension.sources:
            path, ext = os.path.splitext(sfile)
            if ext in ('.pyx', '.py'):
                ext = '.c'
                sfile = path + ext
            sources.append(sfile)
        extension.sources[:] = sources
    return extensions

try:
    from Cython.Build import cythonize
except ImportError:
    # The .c files had better already exist.
    cythonize = _dummy_cythonize

def cythonize1(ext):
    # All the directories we have .pxd files
    # and .h files that are included regardless of
    # embed settings.
    standard_include_paths = [
        'src/gevent',
        'src/gevent/libev',
        'src/gevent/resolver',
        # This is for generated include files; see below.
        '.',
    ]
    if PY311:
        # The "fast" code is Cython for manipulating
        # exceptions is, unfortunately, broken, at least in 3.0.2.
        # The implementation of __Pyx__GetException() doesn't properly set
        # tstate->current_exception when it normalizes exceptions,
        # causing assertion errors.
        # This definitely seems to be a problem on 3.12, and MAY
        # be a problem on 3.11 (#1985)
        ext.define_macros.append(('CYTHON_FAST_THREAD_STATE', '0'))
    try:
        new_ext = cythonize(
            [ext],
            include_path=standard_include_paths,
            annotate=True,
            compiler_directives={
                'language_level': '3str',
                'always_allow_keywords': False,
                'infer_types': True,
                'nonecheck': False,
            },
            # XXX: Cython developers say: "Please use C macros instead
            # of Pyrex defines. Taking this kind of decision based on
            # the runtime environment of the build is wrong, it needs
            # to be taken at C compile time."
            #
            # They also say, "The 'IF' statement is deprecated and
            # will be removed in a future Cython version. Consider
            # using runtime conditions or C macros instead. See
            # https://github.com/cython/cython/issues/4310"
            #
            # And: " The 'DEF' statement is deprecated and will be
            # removed in a future Cython version. Consider using
            # global variables, constants, and in-place literals
            # instead."
            #compile_time_env={
            #
            #},
            # The common_utility_include_dir (not well documented)
            # causes Cython to emit separate files for much of the
            # static support code. Each of the modules then includes
            # the static files they need. They have hash names based
            # on digest of all the relevant compiler directives,
            # including those set here and those set in the file. It's
            # worth monitoring to be sure that we don't start to get
            # divergent copies; make sure files declare the same
            # options.
            #
            # The value used here must be listed in the above ``include_path``,
            # and included in sdists. Files will be included based on this
            # full path, so its parent directory, ``.``, must be on the runtime
            # include path.
            common_utility_include_dir=COMMON_UTILITY_INCLUDE_DIR,
            # The ``cache`` argument is not well documented, but causes Cython to
            # cache to disk some intermediate results. In the past, this was
            # incompatible with ``common_utility_include_dir``, but not anymore.
            # However, it seems to only function on posix (it spawns ``du``).
            # It doesn't seem to buy us much speed, and results in a bunch of
            # ResourceWarnings about unclosed files.
            # cache="build/cycache",
        )[0]
    except ValueError:
        # 'invalid literal for int() with base 10: '3str'
        # This is seen when an older version of Cython is installed.
        # It's a bit of a chicken-and-egg, though, because installing
        # from dev-requirements first scans this egg for its requirements
        # before doing any updates.
        import traceback
        traceback.print_exc()
        new_ext = _dummy_cythonize([ext])[0]

    for optional_attr in ('configure', 'optional'):
        if hasattr(ext, optional_attr):
            setattr(new_ext, optional_attr,
                    getattr(ext, optional_attr))
    new_ext.extra_compile_args.extend(IGNORE_THIRD_PARTY_WARNINGS)
    new_ext.include_dirs.extend(standard_include_paths)
    return new_ext

# A tuple of arguments to add to ``extra_compile_args``
# to ignore warnings from third-party code we can't do anything
# about.
IGNORE_THIRD_PARTY_WARNINGS = ()
if sys.platform == 'darwin':
    # macos, or other platforms using clang
    # (TODO: How to detect clang outside those platforms?)
    IGNORE_THIRD_PARTY_WARNINGS += (
        # If clang is old and doesn't support the warning, these
        # are ignored, albeit not silently.
        # The first two are all over the place from Cython.
        '-Wno-unreachable-code',
        '-Wno-deprecated-declarations',
        # generic, started with some xcode update
        '-Wno-incompatible-sysroot',
        # libuv
        '-Wno-tautological-compare',
        '-Wno-implicit-function-declaration',
        # libev
        '-Wno-unused-value',
        '-Wno-macro-redefined',
    )

## Distutils extensions
class BuildFailed(Exception):
    pass

from distutils.errors import CCompilerError, DistutilsExecError, DistutilsPlatformError # pylint:disable=no-name-in-module,import-error
ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError, IOError)


class ConfiguringBuildExt(build_ext):

    # CFFI subclasses this class with its own, that overrides run()
    # and invokes a `pre_run` method, if defined. The run() method is
    # called only once from setup.py (this class is only instantiated
    # once per invocation of setup()); run() in turn calls
    # `build_extension` for every defined extension.

    # For extensions we control, we let them define a `configure`
    # callable attribute, and we invoke that before building. But we
    # can't control the Extension object that CFFI creates. The best
    # we can do is provide a global hook that we can invoke in pre_run().

    gevent_pre_run_actions = ()

    @classmethod
    def gevent_add_pre_run_action(cls, action):
        # Actions should be idempotent.
        cls.gevent_pre_run_actions += (action,)

    def finalize_options(self):
        # Setting parallel to true can break builds when we need to configure
        # embedded libraries, which we do by changing directories. If that
        # happens while we're compiling, we may not be able to find source code.
        build_ext.finalize_options(self)

    def gevent_prepare(self, ext):
        configure = getattr(ext, 'configure', None)
        if configure:
            configure(self, ext)

    def build_extension(self, ext):
        self.gevent_prepare(ext)
        try:
            return build_ext.build_extension(self, ext)
        except ext_errors:
            if getattr(ext, 'optional', False):
                raise BuildFailed()
            raise

    def pre_run(self, *_args):
        # Called only from CFFI.
        # With mulitple extensions, this probably gets called multiple
        # times.
        for action in self.gevent_pre_run_actions:
            action()


class Extension(_Extension):
    # This class has a few functions:
    #
    #    1. Make pylint happy in terms of attributes we use.
    #    2. Add default arguments, often platform specific.

    def __init__(self, *args, **kwargs):
        self.libraries = []
        self.define_macros = []
        # Python 2 has this as an old-style class for some reason
        # so super() doesn't work.
        _Extension.__init__(self, *args, **kwargs) # pylint:disable=no-member,non-parent-init-called


from distutils.command.clean import clean # pylint:disable=no-name-in-module,import-error
from distutils import log # pylint:disable=no-name-in-module
from distutils.dir_util import remove_tree # pylint:disable=no-name-in-module,import-error

class GeventClean(clean):

    BASE_GEVENT_SRC = os.path.join('src', 'gevent')

    def __find_directories_in(self, top, named=None):
        """
        Iterate directories, beneath and including *top* ignoring '.'
        entries.
        """
        for dirpath, dirnames, _ in os.walk(top):
            # Modify dirnames in place to prevent walk from
            # recursing into hidden directories.
            dirnames[:] = [x for x in dirnames if not x.startswith('.')]
            for dirname in dirnames:
                if named is None or named == dirname:
                    yield os.path.join(dirpath, dirname)

    def __glob_under(self, base, file_pat):
        return glob_many(
            os.path.join(base, file_pat),
            *(os.path.join(x, file_pat)
              for x in
              self.__find_directories_in(base)))

    def __remove_dirs(self, remove_file):

        dirs_to_remove = [
            'htmlcov',
            '.eggs',
            COMMON_UTILITY_INCLUDE_DIR,
        ]
        if self.all:
            dirs_to_remove += [
                # tox
                '.tox',
                # instal.sh for pyenv
                '.runtimes',
                # Built wheels from manylinux
                'wheelhouse',
                # Doc build
                os.path.join('.', 'docs', '_build'),
            ]
        dir_finders = [
            # All python cache dirs
            (self.__find_directories_in, '.', '__pycache__'),
        ]

        for finder in dir_finders:
            func = finder[0]
            args = finder[1:]
            dirs_to_remove.extend(func(*args))

        for f in sorted(dirs_to_remove):
            remove_file(f)

    def run(self):
        clean.run(self)

        if self.dry_run:
            def remove_file(f):
                if os.path.isdir(f):
                    remove_tree(f, dry_run=self.dry_run)
                elif os.path.exists(f):
                    log.info("Would remove '%s'", f)
        else:
            def remove_file(f):
                if os.path.isdir(f):
                    remove_tree(f, dry_run=self.dry_run)
                elif os.path.exists(f):
                    log.info("Removing '%s'", f)
                    os.remove(f)

        # Remove directories first before searching for individual files
        self.__remove_dirs(remove_file)

        def glob_gevent(file_path):
            return glob(os.path.join(self.BASE_GEVENT_SRC, file_path))

        def glob_gevent_and_under(file_pat):
            return self.__glob_under(self.BASE_GEVENT_SRC, file_pat)

        def glob_root_and_under(file_pat):
            return self.__glob_under('.', file_pat)

        files_to_remove = [
            '.coverage',
            # One-off cython-generated code that doesn't
            # follow a globbale-pattern
            os.path.join(self.BASE_GEVENT_SRC, 'libev', 'corecext.c'),
            os.path.join(self.BASE_GEVENT_SRC, 'libev', 'corecext.h'),
            os.path.join(self.BASE_GEVENT_SRC, 'resolver', 'cares.c'),
            os.path.join(self.BASE_GEVENT_SRC, 'resolver', 'cares.c'),
        ]

        def dep_configure_artifacts(dep):
            for f in (
                    'config.h',
                    'config.log',
                    'config.status',
                    'config.cache',
                    'configure-output.txt',
                    '.libs'
            ):
                yield os.path.join('deps', dep, f)

        file_finders = [
            # The base gevent directory contains
            # only generated .c code. Remove it.
            (glob_gevent, "*.c"),
            # Any .html files found in the gevent directory
            # are the result of Cython annotations. Remove them.
            (glob_gevent_and_under, "*.html"),
            # Any compiled binaries have to go
            (glob_gevent_and_under, "*.so"),
            (glob_gevent_and_under, "*.pyd"),
            (glob_root_and_under, "*.o"),
            # Compiled python files too
            (glob_gevent_and_under, "*.pyc"),
            (glob_gevent_and_under, "*.pyo"),

            # Artifacts of building dependencies in place
            (dep_configure_artifacts, 'libev'),
            (dep_configure_artifacts, 'libuv'),
            (dep_configure_artifacts, 'c-ares'),
        ]

        for func, pat in file_finders:
            files_to_remove.extend(func(pat))

        for f in sorted(files_to_remove):
            remove_file(f)
