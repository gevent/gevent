========================
 Installing From Source
========================

If you are unable to use the binary wheels (for platforms where no
pre-built wheels are available or if wheel installation is disabled),
you can build gevent from source. A normal ``pip install`` will
fallback to doing this if no binary wheel is available. (If you'll be
:ref:`developing <development>` gevent, you'll need to install from
source also; follow that link for more details.)


General Notes
=============

- You can force installation of gevent from source with ``pip
  install --no-binary gevent gevent``. This is useful if there is a
  binary wheel available, but you want to change the compile-time
  options, such as to use a system version of libuv instead of the
  embedded version. See :ref:`build-config`.

- You'll need `pip 19 and setuptools 40.8
  <https://pip.pypa.io/en/stable/reference/pip/#pep-517-and-518-support>`_
  with fully functional :pep:`518` and :pep:`517` support to install
  gevent from source.

- You'll need a working C compiler toolchain that can build Python
  extensions. On some platforms, you may need to install Python
  development packages. You'll also need the ability to compile `cffi
  <https://pypi.org/project/cffi/>`_ modules, which may require
  installing FFI development packages. Installing `make
  <https://en.wikipedia.org/wiki/Make_(software)>`_ and other common
  utilities such as `file
  <https://en.wikipedia.org/wiki/File_(command)>`_ may also be
  required.

  For example, on Alpine Linux, one might need to do this::

     apk add --virtual build-deps file make gcc musl-dev libffi-dev

  See :issue:`1567`, :issue:`1559`, and :issue:`1566`.

  .. note::

     The exact set of external dependencies isn't necessarily fixed
     and depends on the configure scripts of the bundled C libraries
     such as libev, libuv and c-ares. Disabling :ref:`embed-lib` and
     using system libraries can reduce these dependencies, although
     this isn't encouraged.

- Installing from source requires ``setuptools``. This is installed
  automatically in virtual environments and by buildout. However,
  gevent uses :pep:`496` environment markers in ``setup.py``.
  Consequently, you'll need a version of setuptools newer than 25
  (mid 2016) to install gevent from source; a version that's too old
  will produce a ``ValueError``. Older versions of pipenv may also
  `have issues installing gevent for this reason
  <https://github.com/pypa/pipenv/issues/2113>`_.

- gevent 1.5 and newer come with a ``pyproject.toml`` file that
  installs the build dependencies, including CFFI (needed for libuv
  support). pip 18 or above is required for this support.

- You can use pip's `VCS support
  <https://pip.pypa.io/en/stable/reference/pip_install/#vcs-support>`_
  to install gevent directly from its code repository. This can be
  useful to check if a bug you're experiencing has been fixed. For
  example, to install the current development version::

    pip install git+git://github.com/gevent/gevent.git#egg=gevent

  Often one would install this way into a virtual environment.

  If you're using pip 18 or above, that should be all you need. If you
  have difficulties, see the development instructions for more information.


Common Installation Issues
==========================

The following are some common installation problems and solutions for
those compiling gevent from source.

- Some Linux distributions are now mounting their temporary
  directories with the ``noexec`` option. This can cause a standard
  ``pip install gevent`` to fail with an error like ``cannot run C
  compiled programs``. One fix is to mount the temporary directory
  without that option. Another may be to use the ``--build`` option to
  ``pip install`` to specify another directory. See `issue #570
  <https://github.com/gevent/gevent/issues/570>`_ and `issue #612
  <https://github.com/gevent/gevent/issues/612>`_ for examples.

- Also check for conflicts with environment variables like ``CFLAGS``.
  For example, see `Library Updates
  <http://www.gevent.org/whatsnew_1_1.html#library-updates-label>`_.

- Users of a recent SmartOS release may need to customize the
  ``CPPFLAGS`` (the environment variable containing the default
  options for the C preprocessor) if they are using the libev shipped
  with gevent. See `Operating Systems
  <http://www.gevent.org/whatsnew_1_1.html#operating-systems-label>`_
  for more information.

- If you see ``ValueError: ("Expected ',' or end-of-list in", "cffi >=
  1.11.5 ; sys_platform == 'win32' and platform_python_implementation
  == 'CPython'", 'at', " ; sys_platform == 'win32' and
  platform_python_implementation == 'CPython'")``, the version of
  setuptools is too old. Install a more recent version of setuptools.

.. _build-config:

Build-Time Configuration
========================

There are a few knobs that can be tweaked at gevent build time. These
are mostly useful for downstream packagers. They all take the form of
environment variables that must be set when ``setup.py`` is called
(note that ``pip install`` will invoke ``setup.py``). Toggle flags
that have boolean values may take the form of 0/1, true/false, off/on,
yes/no.

``CPPFLAGS``
  A standard variable used when building the C extensions. gevent may
  make slight modifications to this variable.
``CFLAGS``
  A standard variable used when building the C extensions. gevent may
  make slight modifications to this variable.
``LDFLAGS``
  A standard variable used when building the C extensions. gevent may
  make slight modifications to this variable.
``GEVENTSETUP_EV_VERIFY``
  If set, the value is passed through as the value of the
  ``EV_VERIFY`` C compiler macro when libev is embedded.

  In general, setting ``CPPFLAGS`` is more general and can contain
  other macros recognized by libev.

.. _embed-lib:

Embedding Libraries
-------------------

By default, gevent builds and embeds tested versions of its C
dependencies libev, libuv, and c-ares. This is the recommended
configuration as the specific versions used are tested by gevent, and
sometimes require patches to be applied. Moreover, embedding,
especially in the case of libev, can be more efficient as features not
needed by gevent can be disabled, resulting in smaller or faster
libraries or runtimes.

However, this can be disabled, either for all libraries at once or for
individual libraries.

When embedding a library is disabled, the library must already be
installed on the system in a way the compiler can access and link
(i.e., correct ``CPPFLAGS``, etc) in order to use the corresponding C
extension.

``GEVENTSETUP_EMBED``
  A boolean defaulting to true. When turned off (e.g.,
  ``GEVENTSETUP_EMBED=0``), libraries are not embedded in the gevent C
  extensions. The value of this is used as the default for all the
  libraries if no more specific version is defined.
``GEVENTSETUP_EMBED_LIBEV``
  Controls embedding libev.
``GEVENTSETUP_EMBED_CARES``
  Controls embedding c-ares.
``GEVENTSETUP_EMBED_LIBUV``
  This is not defined or used, only a CFFI extension is available and
  those are always embedded.

Older versions of gevent supported ``EMBED`` and ``LIBEV_EMBED``, etc,
to mean the same thing. Those aliases still work but are deprecated
and print a warning.
