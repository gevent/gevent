==========================================================
 :mod:`gevent.core` - (deprecated) event loop abstraction
==========================================================

.. automodule:: gevent.core


This module was originally a wrapper around libev_ and followed the
libev API pretty closely. Now that we support libuv, it also serves as
something of an event loop abstraction layer. Most people will not
need to use the objects defined in this module directly. If you need
to create watcher objects, you should use the methods defined on the
current event loop.

Note that gevent creates an event loop transparently for the user and
runs it in a dedicated greenlet (called hub), so using this module is
not necessary. In fact, if you do use it, chances are that your
program is not compatible across different gevent versions (gevent.core
in 0.x has a completely different interface and 2.x will probably have
yet another interface) and implementations (the libev, libev CFFI and
libuv implementations all have different contents in this module).


.. caution::

    Never instantiate the watcher classes defined in this module (if
    they are defined in this module; the various event loop
    implementations do something very different with them). Always use
    the :class:`watcher methods defined <gevent._interfaces.ILoop>`
    on :attr:`the current loop <gevent.hub.Hub.loop>`, i.e.,
    ``get_hub().loop``.


On Windows, this wrapper will accept Windows handles rather than stdio
file descriptors which libev requires. This is to simplify interaction
with the rest of the Python, since it requires Windows handles.




.. _libev: http://software.schmorp.de/pkg/libev.html
