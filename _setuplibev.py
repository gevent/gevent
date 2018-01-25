# -*- coding: utf-8 -*-
"""
setup helpers for libev.
"""

from __future__ import print_function, absolute_import, division

import sys
import os.path

from _setuputils import Extension

from _setuputils import system
from _setuputils import quoted_dep_abspath
from _setuputils import WIN
from _setuputils import make_universal_header
from _setuputils import LIBRARIES
from _setuputils import DEFINE_MACROS
from _setuputils import glob_many
from _setuputils import dep_abspath
from _setuputils import should_embed
from _setuputils import cythonize1


LIBEV_EMBED = should_embed('libev')

# Configure libev in place; but cp the config.h to the old directory;
# if we're building a CPython extension, the old directory will be
# the build/temp.XXX/libev/ directory. If we're building from a
# source checkout on pypy, OLDPWD will be the location of setup.py
# and the PyPy branch will clean it up.
libev_configure_command = ' '.join([
    "(cd ", quoted_dep_abspath('libev'),
    " && sh ./configure ",
    " && cp config.h \"$OLDPWD\"",
    ")",
    '> configure-output.txt'
])


def configure_libev(bext, ext):
    if WIN:
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
        system(libev_configure_command)
        if sys.platform == 'darwin':
            make_universal_header('config.h',
                                  'SIZEOF_LONG', 'SIZEOF_SIZE_T', 'SIZEOF_TIME_T')
    finally:
        os.chdir(cwd)

CORE = Extension(name='gevent.libev.corecext',
                 sources=[
                     'src/gevent/libev/corecext.pyx',
                     'src/gevent/libev/callbacks.c',
                 ],
                 include_dirs=['src/gevent/libev'] + [dep_abspath('libev')] if LIBEV_EMBED else [],
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
    CORE.define_macros += [('LIBEV_EMBED', '1'),
                           ('EV_COMMON', ''),  # we don't use void* data
                           # libev watchers that we don't use currently:
                           ('EV_CLEANUP_ENABLE', '0'),
                           ('EV_EMBED_ENABLE', '0'),
                           ("EV_PERIODIC_ENABLE", '0')]
    CORE.configure = configure_libev
    if sys.platform == "darwin":
        os.environ["CPPFLAGS"] = ("%s %s" % (os.environ.get("CPPFLAGS", ""), "-U__llvm__")).lstrip()
    if os.environ.get('GEVENTSETUP_EV_VERIFY') is not None:
        CORE.define_macros.append(('EV_VERIFY', os.environ['GEVENTSETUP_EV_VERIFY']))
else:
    CORE.libraries.append('ev')

CORE = cythonize1(CORE)
