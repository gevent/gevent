===============================
 Installation and Requirements
===============================

.. _installation:

..
  This file is included in README.rst so it is limited to plain
  ReST markup, not Sphinx.

.. note::

   If you are reading this document on the `Python Package Index`_
   (PyPI, https://pypi.org/), it is specific to the version of gevent that
   you are viewing. If you are viewing this document on gevent.org, it
   refers to the current state of gevent in source control (git
   master).

Supported Platforms
===================

This version of gevent runs on Python 3.8 and up, (for exact details
of tested versions, see the classifiers on the PyPI page or in
``setup.py``). gevent requires the `greenlet
<https://greenlet.readthedocs.io>`_ library and will install the
`cffi`_ library by default on Windows. The cffi library will become
the default on all platforms in a future release of gevent.

This version of gevent is also tested on on PyPy 3.10 (7.3.12); it
should run on PyPy 3.9 and above. On PyPy, there are no external
dependencies.

gevent is tested on Windows, macOS, and Linux, and should run on most
other Unix-like operating systems (e.g., FreeBSD, Solaris, etc.)

.. note::

   Windows is supported as a tier 2, "best effort," platform. It is
   suitable for development, but not recommended for production. In
   particular, PyPy3 on Windows may have issues, especially with
   subprocesses.

   On Windows using the deprecated libev backend, gevent is
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
|3.5.x  | 20.9.0|
|       |       |
|       |       |
+-------+-------+
|2.7.9 -|       |
|2.7.18,| 22.10 |
|3.6,   |       |
|3.7    |       |
|       |       |
+-------+-------+

Installation
============

.. note::

   This section is about installing released versions of gevent as
   distributed on the `Python Package Index`_. For building gevent
   from source, including customizing the build and embedded
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

.. tip::

   While the x86-64 binaries are considered production quality, they
   are built with relatively low optimization levels and no hardware
   specific optimizations. Serious production users are encouraged to
   install from source with appropriate compiler flags.

.. tip::

   Beginning with gevent 20.12.0, 64-bit ARM binaries are distributed
   on PyPI for aarch64 manylinux2014 compatible systems. Installing these
   needs a very recent version of ``pip``. These wheels *do not*
   contain the c-ares resolver, are not tested, and are built with
   very low levels of optimizations. Serious production users of
   gevent on 64-bit ARM systems are encouraged to build their own
   binary wheels.

   Beginning with gevent 22.10.0, ppc64le binaries are distributed on
   PyPI. The same caveats apply as for 64-bit ARM binaries. Using them
   for anything other than local development is discouraged.

   Beginning with gevent 23, muslinux aarch64 and S390X binaries
   are distributed on PyPI. The same caveats apply as for 64-bit ARM
   binaries. Using them for anything other than local development is
   discouraged.


Installing From Source
----------------------

If you are unable to use the binary wheels (for platforms where no
pre-built wheels are available or if wheel installation is disabled),
you can build gevent from source. A normal ``pip install`` will
fall back to doing this if no binary wheel is available. See
`Installing From Source`_ for more, including common installation issues.

Extra Dependencies
==================

There are a number
of additional libraries that extend gevent's functionality and will be
used if they are available. All of these may be installed using
`setuptools extras
<https://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies>`_,
as named below, e.g., ``pip install gevent[events]``.

events
    In versions of gevent up to and including 20.5.0, this provided configurable
    event support using `zope.event
    <https://pypi.org/project/zope.event>`_ and was highly
    recommended.

    In versions after that, this extra is empty and does nothing. It
    will be removed in gevent 21.0.

dnspython
    Enables a pure-Python resolver, backed by `dnspython
    <https://pypi.org/project/dnspython>`_. On Python 2, this also
    includes `idna <https://pypi.org/project/idna>`_. They can be
    installed with the ``dnspython`` extra.

    .. note:: This is not compatible with Python 3.10+ or dnspython 2.

monitor
    Enhancements to gevent's self-monitoring capabilities. This
    includes the `psutil <https://pypi.org/project/psutil>`_ library
    which is needed to monitor memory usage. (Note that this may not
    build on all platforms.)

recommended
    A shortcut for installing suggested extras together. This includes
    the non-test extras defined here, plus additions that improve
    gevent's operation on certain platforms (for example, in the past,
    it has included backports of newer APIs).

test
    Everything needed to run the complete gevent test suite.


.. _`pip`: https://pip.pypa.io/en/stable/installing/
.. _`wheels`: http://pythonwheels.com
.. _`gevent 1.5`: whatsnew_1_5.html
.. _`Installing From Source`: https://www.gevent.org/development/installing_from_source.html

.. _`cffi`: https://cffi.readthedocs.io
.. _`limitations in libev`: http://pod.tst.eu/http://cvs.schmorp.de/libev/ev.pod#WIN32_PLATFORM_LIMITATIONS_AND_WORKA
