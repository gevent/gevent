================================
 Managing Embedded Dependencies
================================

- Modify the c-ares Makefile.in[c] to empty out the MANPAGES variables
  so that we don't have to ship those in the sdist.

  XXX: We need a patch for that.



Updating libuv
==============

- Clean up the libuv tree, and apply the patches to libuv (this whole
  sequence is meant to be copied and pasted into the terminal)::

    export LIBUV_VER=v1.27.0

    cd deps/
    wget https://dist.libuv.org/dist/$LIBUV_VER/libuv-$LIBUV_VER.tar.gz
    tar -xf libuv-$LIBUV_VER.tar.gz
    rm -rf libuv
    mv libuv-$LIBUV_VER libuv
    rm -rf libuv/.github
    rm -rf libuv/docs
    rm -rf libuv/samples
    rm -rf libuv/test
    rm -rf libuv/tools
    rm -f libuv/android-configure*
    git apply libuv-win-binary.patch

At this point there might be new files in libuv that need added to git
and the build process. Evaluate those and add them to git and to
``src/gevent/libuv/_corecffi_build.py`` as needed. Then check if there
are changes to the build system (e.g., the .gyp files) that need to be
accounted for in our build file.
