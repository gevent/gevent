- Modify the c-ares Makefile.in[c] to empty out the MANPAGES variables
  so that we don't have to ship those in the sdist.

  XXX: We need a patch for that.

- Apply the gevent-libuv.patch to updates of libuv.

- Clean up the libuv tree:
  - rm -rf libuv/.github
  - rm -rf libuv/docs
  - rm -rf libuv/samples
  - rm -rf libuv/test
  - rm -rf libuv/tools
