Make worker threads created by :class:`gevent.threadpool.ThreadPool` install
the :func:`threading.setprofile` and :func:`threading.settrace` hooks
while tasks are running. This provides visibility to profiling and
tracing tools like yappi.

Reported by Suhail Muhammed.
