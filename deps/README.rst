================================
 Managing Embedded Dependencies
================================


Updating libev
==============

Download and unpack the tarball into libev/. Remove these extra
files::

  rm -f libev/Makefile.am
  rm -f libev/Symbols.ev
  rm -f libev/Symbols.event
  rm -f libev/TODO
  rm -f libev/aclocal.m4
  rm -f libev/autogen.sh
  rm -f libev/compile
  rm -f libev/configure.ac
  rm -f libev/libev.m4
  rm -f libev/mkinstalldirs


Check if 'config.guess' and/or 'config.sub' went backwards in time
(the 'timestamp' and copyright dates'). If so, revert it (or update
from the latest source
http://git.savannah.gnu.org/gitweb/?p=config.git;a=tree )

Updating c-ares
===============

- Modify the c-ares Makefile.in[c] to empty out the MANPAGES variables
  so that we don't have to ship those in the sdist.

  XXX: We need a patch for that.

- Follow the same 'config.guess' and 'config.sub' steps as libev.


Updating libuv
==============

- Clean up the libuv tree, and apply the patches to libuv (this whole
  sequence is meant to be copied and pasted into the terminal)::

    export LIBUV_VER=v1.27.0

    cd deps/
    wget https://dist.libuv.org/dist/$LIBUV_VER/libuv-$LIBUV_VER.tar.gz
    tar -xf libuv-$LIBUV_VER.tar.gz
    rm libuv-$LIBUV_VER.tar.gz
    rm -rf libuv
    mv libuv-$LIBUV_VER libuv
    rm -rf libuv/.github
    rm -rf libuv/docs
    rm -rf libuv/samples
    rm -rf libuv/test/*.[ch] libuv/test/test.gyp # must leave the fixtures/ dir
    rm -rf libuv/tools
    rm -f libuv/android-configure*
    git apply libuv-win-binary.patch

At this point there might be new files in libuv that need added to git
and the build process. Evaluate those and add them to git and to
``src/gevent/libuv/_corecffi_build.py`` as needed. Then check if there
are changes to the build system (e.g., the .gyp files) that need to be
accounted for in our build file.

- Follow the same 'config.guess' and 'config.sub' steps as libev.
