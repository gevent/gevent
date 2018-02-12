"""
Wrappers to make file-like objects cooperative.

.. class:: FileObject

   The main entry point to the file-like gevent-compatible behaviour. It will be defined
   to be the best available implementation.

There are two main implementations of ``FileObject``. On all systems,
there is :class:`FileObjectThread` which uses the built-in native
threadpool to avoid blocking the entire interpreter. On UNIX systems
(those that support the :mod:`fcntl` module), there is also
:class:`FileObjectPosix` which uses native non-blocking semantics.

A third class, :class:`FileObjectBlock`, is simply a wrapper that executes everything
synchronously (and so is not gevent-compatible). It is provided for testing and debugging
purposes.

Configuration
=============

You may change the default value for ``FileObject`` using the
``GEVENT_FILE`` environment variable. Set it to ``posix``, ``thread``,
or ``block`` to choose from :class:`FileObjectPosix`,
:class:`FileObjectThread` and :class:`FileObjectBlock`, respectively.
You may also set it to the fully qualified class name of another
object that implements the file interface to use one of your own
objects.

.. note:: The environment variable must be set at the time this module
   is first imported.

Classes
=======
"""
from __future__ import absolute_import

from gevent._config import config

__all__ = [
    'FileObjectPosix',
    'FileObjectThread',
    'FileObjectBlock',
    'FileObject',
]

try:
    from fcntl import fcntl
except ImportError:
    __all__.remove("FileObjectPosix")
else:
    del fcntl
    from gevent._fileobjectposix import FileObjectPosix

from gevent._fileobjectcommon import FileObjectThread
from gevent._fileobjectcommon import FileObjectBlock


# None of the possible objects can live in this module because
# we would get an import cycle and the config couldn't be set from code.
FileObject = config.fileobject
