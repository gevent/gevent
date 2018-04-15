:mod:`gevent.core` - event loop based on libev
==============================================

.. automodule:: gevent.core


This module is a wrapper around libev__ and follower the libev API pretty closely. Note,
that gevent creates an event loop transparently for the user and runs it in a dedicated
greenlet (called hub), so using this module is not necessary. In fact, if you do use it,
chances are that your program is not compatible across different gevent version (gevent.core in
0.x has a completely different interface and 2.x will probably have yet another interface).

On Windows, this wrapper will accept Windows handles rather than stdio file descriptors which libev requires. This is to simplify
interaction with the rest of the Python, since it requires Windows handles.

The current event loop can be obtained with ``gevent.get_hub().loop``.


__ http://pod.tst.eu/http://cvs.schmorp.de/libev/ev.pod


events
------

.. autoclass:: loop(flags=None, default=True)
    :members:
    :undoc-members:


misc functions
--------------

.. autofunction:: get_version
.. autofunction:: get_header_version
.. autofunction:: supported_backends
.. autofunction:: recommended_backends
.. autofunction:: embeddable_backends
.. autofunction:: time

