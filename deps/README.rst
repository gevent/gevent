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

   rm -rf libuv/.github
   rm -rf libuv/docs
   rm -rf libuv/samples
   rm -rf libuv/test
   rm -rf libuv/tools
   rm -f libuv/android-configure*
   git apply libuv-win-binary.patch
