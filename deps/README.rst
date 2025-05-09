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
(the 'timestamp' and 'copyright' dates). If so, revert it (or update
from the latest source
https://git.savannah.gnu.org/gitweb/?p=config.git;a=tree )

Updating c-ares
===============

- Download and clean up the c-ares Makefile.in[c] and configure script to empty out the
  MANPAGES variables so that we don't have to ship those in the sdist::

    export CARES_VER=1.33.1

    cd deps/
    wget https://github.com/c-ares/c-ares/releases/download/v$CARES_VER/c-ares-$CARES_VER.tar.gz
    tar -xf c-ares-$CARES_VER.tar.gz
    rm -rf c-ares c-ares-$CARES_VER.tar.gz
    mv c-ares-$CARES_VER c-ares
    cp c-ares/include/ares_build.h c-ares/include/ares_build.h.dist
    rm -rf c-ares/docs
    rm -rf c-ares/test
    rm -rf c-ares/cmake
    rm -f c-ares/maketgz
    rm -f c-ares/CMakeLists.txt
    rm -f c-ares/RELEASE-PROCEDURE.md c-ares/CONTRIBUTING.md c-ares/SECURITY.md
    rm -f c-ares/*.cmake c-ares/*.cmake.in
    rm -rf c-ares/config/
    rm -f c-ares/INSTALL.md c-ares/LICENSE.md 	c-ares/DEVELOPER-NOTES.md
    rm -f c-ares/buildconf.bat
    rm -f c-ares/Makefile*
    git apply cares-make.patch

  At this point there might be new files in c-ares that need added to
  git, evaluate them and add them.

  Note that the patch may not apply cleanly. If not, commit the
  changes before the patch. Then manually apply them by editing the
  three files to remove the references to ``docs`` and ``test``; this
  is easiest to do by reading the existing patch file and searching
  for the relevant lines in the target files. Once this is working
  correctly, create the new patch using ``git diff -p --minimal -w``
  (note that you cannot directly redirect the output of this into
  ``cares-make.patch``, or you'll get the diff of the patch itself in
  the diff!).

- Follow the same 'config.guess' and 'config.sub' steps as libev,
  except the files belong in the ``config/`` subdir.


Updating libuv
==============

- Clean up the libuv tree, and apply the patches to libuv (this whole
  sequence is meant to be copied and pasted into the terminal)::

    export LIBUV_VER=v1.38.0

    cd deps/
    wget https://dist.libuv.org/dist/$LIBUV_VER/libuv-$LIBUV_VER.tar.gz
    tar -xf libuv-$LIBUV_VER.tar.gz
    rm libuv-$LIBUV_VER.tar.gz
    rm -rf libuv
    mv libuv-$LIBUV_VER libuv
    rm -rf libuv/.github
    rm -rf libuv/.readthedocs.yaml
    rm -rf libuv/LINKS.md
    rm -rf libuv/docs
    rm -rf libuv/samples
    rm -rf libuv/test/*.[ch] libuv/test/test.gyp # must leave the fixtures/ dir
    rm -rf libuv/tools
    rm -f libuv/android-configure*
    rm -f libuv/uv_win_longpath.manifest
    rm -rf libuv/cmake-toolchains/

At this point there might be new files in libuv that need added to git
and the build process. Evaluate those and add them to git and to
``src/gevent/libuv/_corecffi_build.py`` as needed. Then check if there
are changes to the build system (e.g., the .gyp files) that need to be
accounted for in our build file.

.. caution::

   Pay special attention to the m4 directory. New .m4 files that need
   to be added may not actually show up in git output. See
   https://github.com/libuv/libuv/issues/2862

- Follow the same 'config.guess' and 'config.sub' steps as libev.
- Beginning with libuv 1.49, you must edit ``src/unix/kqueue.c``. In
  the function ``uv__io_check_fd``, there should be two blocks that
  check the file descriptor type on FreeBSD and Apple platforms,
  returning EINVAL for regular files and pipes. ``#if 0`` out those
  blocks. If you don't do this, ``test__fileobject.py`` will fail
  (obviously our tested use cases don't involve the supposed issues
  being fixed by those blocks).
