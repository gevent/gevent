========================
 Installing From Source
========================

If you are unable to use the binary wheels (for platforms where no
pre-built wheels are available or if wheel installation is disabled),
you can build gevent from source. A normal ``pip install`` will
fallback to doing this if no binary wheel is available. See
`Installing From Source <installing-from-source>`_ for more.


- You can force installation of gevent from source with ``pip
  install --no-binary gevent gevent``. This is useful if there is a
  binary wheel available, but you want to change the compile-time
  options, such as to use a system version of libuv instead of the
  embedded version. See ``

- You'll need a working C compiler that can build Python extensions.
  On some platforms, you may need to install Python development
  packages.

- Installing from source requires ``setuptools``. This is installed
  automatically in virtual environments and by buildout. However,
  gevent uses :pep:`496` environment markers in ``setup.py``.
  Consequently, you'll need a version of setuptools newer than 25
  (mid 2016) to install gevent from source; a version that's too old
  will produce a ``ValueError``. Older versions of pipenv may also
  `have issues installing gevent for this reason
  <https://github.com/pypa/pipenv/issues/2113>`_.

- gevent comes with a ``pyproject.toml`` file that installs the build
  dependencies, including CFFI (needed for libuv support). pip 18 or
  above is required for this support.


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

- Also check for conflicts with environment variables like ``CFLAGS``. For
  example, see `Library Updates <http://www.gevent.org/whatsnew_1_1.html#library-updates-label>`_.

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
