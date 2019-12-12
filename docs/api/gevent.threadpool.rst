
=====================================================
 :mod:`gevent.threadpool` - A pool of native threads
=====================================================

.. currentmodule:: gevent.threadpool

.. autoclass:: ThreadPool
    :inherited-members:
    :members: imap, imap_unordered, map, map_async, apply_async, kill,
              join, spawn

    .. method:: apply(func, args=None, kwds=None)

       Rough equivalent of the :func:`apply()` builtin function,
       blocking until the result is ready and returning it.

       The ``func`` will *usually*, but not *always*, be run in a way
       that allows the current greenlet to switch out (for example,
       in a new greenlet or thread, depending on implementation). But
       if the current greenlet or thread is already one that was
       spawned by this pool, the pool may choose to immediately run
       the `func` synchronously.

       .. note:: As implemented, attempting to use
          :meth:`Threadpool.apply` from inside another function that
          was itself spawned in a threadpool (any threadpool) will
          cause the function to be run immediately.

       .. versionchanged:: 1.1a2
          Now raises any exception raised by *func* instead of
          dropping it.

.. autoclass:: ThreadPoolExecutor
