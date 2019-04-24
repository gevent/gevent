============================================
 :mod:`gevent.queue` -- Synchronized queues
============================================

.. automodule:: gevent.queue
    :members:
    :undoc-members:

.. exception:: Full

    An alias for :class:`Queue.Full`

.. exception:: Empty

    An alias for :class:`Queue.Empty`

Examples
========

Example of how to wait for enqueued tasks to be completed::

   def worker():
       while True:
           item = q.get()
           try:
               do_work(item)
           finally:
               q.task_done()

   q = JoinableQueue()
   for i in range(num_worker_threads):
        gevent.spawn(worker)

   for item in source():
       q.put(item)

   q.join()  # block until all tasks are done
