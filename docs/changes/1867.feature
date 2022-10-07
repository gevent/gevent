Added preliminary support for Python 3.11 (rc2 and later).

Some platforms may or may not have binary wheels at this time.

.. important:: Support for legacy versions of Python, including 2.7
               and 3.6, will be ending soon. The
               maintenance burden has become too great and the
               maintainer's time is too limited.

               Ideally, there will be a release of gevent compatible
               with a final release of greenlet 2.0 that still
               supports those legacy versions, but that may not be
               possible; this may be the final release to support them.

:class:`gevent.threadpool.ThreadPool` can now optionally expire idle
threads. This is used by default in the implicit thread pool used for
DNS requests and other user-submitted tasks; other uses of a
thread-pool need to opt-in to this.
