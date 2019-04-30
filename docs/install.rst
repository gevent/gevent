===============================
 Installation and Requirements
===============================

.. _installation:

..
  This file is included in README.rst so it is limited to plain
  ReST markup, not Sphinx.

Supported Platforms
===================

`gevent 1.5`_ runs on Python 2.7.9 and up, and Python 3.5, 3.6 and
3.7. gevent requires the `greenlet <https://greenlet.readthedocs.io>`_
library and will install the `cffi`_ library by default on Windows.
The cffi library will become the default on all platforms in a future
release of gevent.

gevent 1.5 also runs on PyPy 7.0 or above. On PyPy, there are no
external dependencies.

gevent is tested on Windows, macOS, and Linux, and should run on most
other Unix-like operating systems (e.g., FreeBSD, Solaris, etc.)

.. note:: On Windows using the deprecated libev backend, gevent is
          limited to a maximum of 1024 open sockets due to
          `limitations in libev`_. This limitation should not exist
          with the default libuv backend.

Older Versions of Python
------------------------

Users of older versions of Python 2 or Python 3 may install an older
version of gevent. Note that these versions are generally not
supported.

+-------+-------+
|Python |Gevent |
|Version|Version|
+=======+=======+
|2.5    |1.0.x  |
|       |       |
+-------+-------+
|2.6    |1.1.x  |
+-------+-------+
|<=     |1.2.x  |
|2.7.8  |       |
+-------+-------+
|3.3    |1.2.x  |
+-------+-------+
|3.4.0 -| 1.3.x |
|3.4.2  |       |
|       |       |
+-------+-------+
|3.4.3  | 1.4.x |
|       |       |
|       |       |
+-------+-------+


Installation
============

.. note::

   This section is about installing released versions of gevent as
   distributed on the `Python Package Index`_. For developing with
   gevent, including running tests, see `development`_. For building
   gevent from source, including customizing the build and embedded
   libraries, see `Installing From Source`_.

.. _Python Package Index: http://pypi.org/project/gevent

gevent and greenlet can both be installed with `pip`_, e.g., ``pip
install gevent``. Installation using `buildout
<http://docs.buildout.org/en/latest/>`_ is also supported.

On Windows, macOS, and Linux, both gevent and greenlet are
distributed as binary `wheels`_.

.. tip::

   You need Pip 8.0 or later, or buildout 2.10.0 to install the binary
   wheels on Windows or macOS. On Linux, you'll need `pip 19
   <https://github.com/pypa/pip/pull/5008>`_ to install the
   manylinux2010 wheels.


Installing From Source
----------------------

If you are unable to use the binary wheels (for platforms where no
pre-built wheels are available or if wheel installation is disabled),
you can build gevent from source. A normal ``pip install`` will
fall back to doing this if no binary wheel is available. See
`Installing From Source`_ for more, including common installation issues.


Extra Dependencies
==================

gevent has no runtime dependencies outside the standard library,
greenlet, and (on some platforms) `cffi`_. However, there are a number
of additional libraries that extend gevent's functionality and will be
used if they are available. All of these may be installed using
`setuptools extras
<https://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies>`_,
as named below, e.g., ``pip install gevent[events]``.

events
    Configurable event support using `zope.event
    <https://pypi.org/project/zope.event>`_ is highly recommended for
    configurable event support.

dnspython
    Enables the new pure-Python resolver, backed by `dnspython
    <https://pypi.org/project/dnspython>`_. On Python 2, this also
    includes `idna <https://pypi.org/project/idna>`_. They can be
    installed with the ``dnspython`` extra.

monitor
    Enhancements to gevent's self-monitoring capabilities. This
    includes the `psutil <https://pypi.org/project/psutil>`_ library
    which is needed to monitor memory usage. (Note that this may not
    build on all platforms.)

recommended
    A shortcut for installing suggested extras together.

test
    Everything needed to run the complete gevent test suite.


Development
===========

For development information, including installing from git and running
tests, see `development`_.


.. _`pip`: https://pip.pypa.io/en/stable/installing/
.. _`wheels`: http://pythonwheels.com
.. _`gevent 1.5`: whatsnew_1_5.html
.. _`development`: development.html
.. _`Installing From Source`: installing_from_source.html

.. _`cffi`: https://cffi.readthedocs.io
.. _`limitations in libev`: http://pod.tst.eu/http://cvs.schmorp.de/libev/ev.pod#WIN32_PLATFORM_LIMITATIONS_AND_WORKA
