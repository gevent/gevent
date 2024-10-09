Add support for Python 3.13.

- The functions and classes in ``gevent.subprocess`` no longer accept
  ``stdout=STDOUT`` and raise a ``ValueError``.

Several additions and changes to the ``queue`` module, including:

- ``Queue.shutdown`` is available on all versions of Python.
- ``LifoQueue`` is now a joinable queue.
