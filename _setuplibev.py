# -*- coding: utf-8 -*-
"""
setup helpers for libev.

Importing this module should have no side-effects; in particular,
it shouldn't attempt to cythonize anything.
"""

from __future__ import print_function, absolute_import, division

import os.path

from _setuputils import Extension

from _setuputils import system
from _setuputils import dep_abspath
from _setuputils import quoted_dep_abspath
from _setuputils import WIN
from _setuputils import LIBRARIES
from _setuputils import DEFINE_MACROS
from _setuputils import glob_many
from _setuputils import should_embed
from _setuputils import get_include_dirs


LIBEV_EMBED = should_embed('libev')

# Configure libev in place
libev_configure_command = ' '.join([
    "(cd ", quoted_dep_abspath('libev'),
    " && sh ./configure -C > configure-output.txt",
    ")",
])


def configure_libev(build_command=None, extension=None): # pylint:disable=unused-argument
    # build_command is an instance of ConfiguringBuildExt.
    # extension is an instance of the setuptools Extension object.
    #
    # This is invoked while `build_command` is in the middle of its `run()`
    # method.

    # Both of these arguments are unused here so that we can use this function
    # both from a build command and from libev/_corecffi_build.py

    if WIN:
        return

    libev_path = dep_abspath('libev')
    config_path = os.path.join(libev_path, 'config.h')
    if os.path.exists(config_path):
        print("Not configuring libev, 'config.h' already exists")
        return

    system(libev_configure_command)


def build_extension():
    # Return the un-cythonized extension.
    # This can be used to access things like `libraries` and `include_dirs`
    # and `define_macros` so we DRY.
    include_dirs = get_include_dirs()
    include_dirs.append(os.path.abspath(os.path.join('src', 'gevent', 'libev')))
    if LIBEV_EMBED:
        include_dirs.append(dep_abspath('libev'))
    CORE = Extension(name='gevent.libev.corecext',
                     sources=[
                         'src/gevent/libev/corecext.pyx',
                         'src/gevent/libev/callbacks.c',
                     ],
                     include_dirs=include_dirs,
                     libraries=list(LIBRARIES),
                     define_macros=list(DEFINE_MACROS),
                     depends=glob_many('src/gevent/libev/callbacks.*',
                                       'src/gevent/libev/stathelper.c',
                                       'src/gevent/libev/libev*.h',
                                       'deps/libev/*.[ch]'))
    if WIN:
        CORE.define_macros.append(('EV_STANDALONE', '1'))
    # QQQ libev can also use -lm, however it seems to be added implicitly

    if LIBEV_EMBED:
        CORE.define_macros += [
            ('LIBEV_EMBED', '1'),
            # we don't use void* data in the cython implementation;
            # the CFFI implementation does and removes this line.
            ('EV_COMMON', ''),
            # libev watchers that we don't use currently:
            ('EV_CLEANUP_ENABLE', '0'),
            ('EV_EMBED_ENABLE', '0'),
            ("EV_PERIODIC_ENABLE", '0')
        ]
        CORE.configure = configure_libev
        if os.environ.get('GEVENTSETUP_EV_VERIFY') is not None:
            CORE.define_macros.append(
                ('EV_VERIFY', os.environ['GEVENTSETUP_EV_VERIFY']))
            # EV_VERIFY is implemented using assert(), which only works if
            # NDEBUG is *not* defined. distutils likes to define NDEBUG by default,
            # meaning that we get no verification in embedded mode. Since that's the
            # most common testing configuration, that's not good.
            CORE.undef_macros.append('NDEBUG')
    else:
        CORE.define_macros += [('LIBEV_EMBED', '0')]
        CORE.libraries.append('ev')
        CORE.configure = lambda *args: print("libev not embedded, not configuring")

    return CORE
