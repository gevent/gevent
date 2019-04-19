================================
 Managing Embedded Dependencies
================================

* Generate patches with ``git diff --patch --minimal -b``

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

- Download and clean up the c-ares Makefile.in[c] to empty out the
  MANPAGES variables so that we don't have to ship those in the sdist::

    export CARES_VER=1.15.0

    cd deps/
    wget https://c-ares.haxx.se/download/c-ares-$CARES_VER.tar.gz
    tar -xf c-ares-$CARES_VER.tar.gz
    rm -rf c-ares c-ares-$CARES_VER.tar.gz
    mv c-ares-$CARES_VER c-ares
    cp c-ares/ares_build.h c-ares/ares_build.h.dist
    rm -f c-ares/*.3 c-ares/*.1
    rm -rf c-ares/test
    rm -rf c-ares/vc
    rm -f c-ares/maketgz
    rm -f c-ares/CMakeLists.txt
    rm -f c-ares/RELEASE-PROCEDURE.md
    rm -f c-ares/*.cmake c-ares/*.cmake.in
    git apply cares-make.patch

  At this point there might be new files in libuv that need added to
  git, evaluate them and add them.

- Evaluate whether the release has
  https://github.com/c-ares/c-ares/issues/246 fixed. If not, ``git
  apply cares-win32.patch``. If so, then delete that file and this
  part of the instructions.

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
