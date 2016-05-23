# -*- coding: utf-8 -*-
"""
setup helpers for c-ares.
"""

from __future__ import print_function, absolute_import, division

import os
import os.path
import shutil
import sys

from _setuputils import Extension

import distutils.sysconfig  # to get CFLAGS to pass into c-ares configure script pylint:disable=import-error

from _setuputils import WIN
from _setuputils import quoted_dep_abspath
from _setuputils import system
from _setuputils import make_universal_header
from _setuputils import should_embed
from _setuputils import LIBRARIES
from _setuputils import DEFINE_MACROS
from _setuputils import glob_many
from _setuputils import dep_abspath


CARES_EMBED = should_embed('c-ares')


# See #616, trouble building for a 32-bit python against a 64-bit platform
_config_vars = distutils.sysconfig.get_config_var("CFLAGS")
if _config_vars and "m32" in _config_vars:
    _m32 = 'CFLAGS="' + os.getenv('CFLAGS', '') + ' -m32" '
else:
    _m32 = ''

# Use -r, not -e, for support of old solaris. See
# https://github.com/gevent/gevent/issues/777
ares_configure_command = ' '.join([
    "(cd ", quoted_dep_abspath('c-ares'),
    " && if [ -r ares_build.h ]; then cp ares_build.h ares_build.h.orig; fi ",
    " && sh ./configure --disable-dependency-tracking " + _m32 + "CONFIG_COMMANDS= ",
    " && cp ares_config.h ares_build.h \"$OLDPWD\" ",
    " && mv ares_build.h.orig ares_build.h)",
    "> configure-output.txt"])



def configure_ares(bext, ext):
    bdir = os.path.join(bext.build_temp, 'c-ares')
    ext.include_dirs.insert(0, bdir)

    if not os.path.isdir(bdir):
        os.makedirs(bdir)

    if WIN:
        shutil.copy("deps\\c-ares\\ares_build.h.dist", os.path.join(bdir, "ares_build.h"))
        return

    cwd = os.getcwd()
    os.chdir(bdir)
    try:
        if os.path.exists('ares_config.h') and os.path.exists('ares_build.h'):
            return
        try:
            system(ares_configure_command)
        except:
            with open('configure-output.txt', 'r') as t:
                print(t.read(), file=sys.stderr)
            raise
        if sys.platform == 'darwin':
            make_universal_header('ares_build.h', 'CARES_SIZEOF_LONG')
            make_universal_header('ares_config.h', 'SIZEOF_LONG', 'SIZEOF_SIZE_T', 'SIZEOF_TIME_T')
    finally:
        os.chdir(cwd)


ARES = Extension(name='gevent.ares',
                 sources=['src/gevent/gevent.ares.c'],
                 include_dirs=[dep_abspath('c-ares')] if CARES_EMBED else [],
                 libraries=list(LIBRARIES),
                 define_macros=list(DEFINE_MACROS),
                 depends=glob_many('src/gevent/dnshelper.c',
                                   'src/gevent/cares_*.[ch]'))
ARES.optional = True


if CARES_EMBED:
    ARES.sources += glob_many('deps/c-ares/*.c')
    # Strip the standalone binaries that would otherwise
    # cause linking issues
    for bin_c in ('acountry', 'adig', 'ahost'):
        try:
            ARES.sources.remove('deps/c-ares/' + bin_c + '.c')
        except ValueError:
            pass
    ARES.configure = configure_ares
    if WIN:
        ARES.libraries += ['advapi32']
        ARES.define_macros += [('CARES_STATICLIB', '')]
    else:
        ARES.define_macros += [('HAVE_CONFIG_H', '')]
        if sys.platform != 'darwin':
            ARES.libraries += ['rt']
    ARES.define_macros += [('CARES_EMBED', '1')]
else:
    ARES.libraries.append('cares')
    ARES.define_macros += [('HAVE_NETDB_H', '')]
