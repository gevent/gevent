================================
 Managing Embedded Dependencies
================================

- Modify the c-ares Makefile.in[c] to empty out the MANPAGES variables
  so that we don't have to ship those in the sdist.

  XXX: We need a patch for that.



Updating libuv
==============

- Apply the gevent-libuv.patch to updates of libuv.

   [deps] $ patch -p0 < gevent-libuv.patch

- Clean up the libuv tree:
  - rm -rf libuv/.github
  - rm -rf libuv/docs
  - rm -rf libuv/samples
  - rm -rf libuv/test
  - rm -rf libuv/tools

- Create new patches by downloading the source tarball:

   [deps] $ tar -xf libuv-v1.20.1.tar.gz
   [deps] $ diff -r -u libuv-v1.20.1/ libuv > gevent-libuv.patch
