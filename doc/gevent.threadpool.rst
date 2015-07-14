
:mod:`gevent.threadpool`
========================

.. currentmodule:: gevent.threadpool

.. autoclass:: ThreadPool
    :members: imap, imap_unordered, map, map_async, apply_async, kill,
              join, spawn

    .. method:: apply(func, args=None, kwds=None)

       Rough equivalent of the :func:`apply` builtin, blocking until
       the result is ready and returning it.

       .. warning:: As implemented, attempting to use
          :meth:`Threadpool.appy` from inside another function that
          was itself spawned in a threadpool (any threadpool) will
          lead to the hub throwing LoopExit.
