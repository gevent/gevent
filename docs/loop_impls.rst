=============================================
 Event Loop Implementations: libuv and libev
=============================================

.. versionadded:: 1.3

gevent offers a choice of two event loop libraries (`libev`_ and
`libuv`_) and three event loop implementations. This document will
explore those implementations and compare them to each other.

Using A Non-Default Loop
========================

First, we will describe how to choose an event loop other than the
default loop for a given platform. This is done by setting the
``GEVENT_LOOP`` environment variable before starting the program, or
by setting :attr:`gevent.config.loop <gevent._config.Config.loop>` in
code.

.. important::

   If you choose to configure the loop in Python code, it must be done
   *immediately* after importing gevent and before any other gevent
   imports or asynchronous operations are done, preferably at the top
   of your program, right above monkey-patching (if done)::

       import gevent
       gevent.config.loop = "libuv"

.. important::

   In gevent 1.4 and 1.3, if you install gevent from a manylinux1
   binary wheel as distributed on PyPI, you will not be able to use
   the libuv loop. You'll need to compile from source to gain access
   to libuv. gevent 1.5 distributes manylinux2010 wheels which have
   libuv support.

   If you use a Linux distribution's package of gevent, you may or may
   not have any other loops besides the default.


Loop Implementations
====================

Here we will describe the available loop implementations.

+----------+-------+------------+------------+-----+--------------+---------+--------+
|Name      |Library|Default     |Interpreters|Age  |Implementation|Build    |Embedded|
|          |       |            |            |     |              |Status   |        |
+==========+=======+============+============+=====+==============+=========+========+
|libev     |libev  |CPython on  |CPython only|8    |Cython        |Default  |Default;|
|          |       |non-Windows |            |years|              |         |optional|
|          |       |platforms   |            |     |              |         |        |
+----------+-------+------------+------------+-----+--------------+---------+--------+
|libev-cffi|libev  |PyPy on     |CPython and |4    |CFFI          |Optional;|Default;|
|          |       |non-Windows |PyPy        |years|              |default  |optional|
|          |       |platforms   |            |     |              |         |        |
+----------+-------+------------+------------+-----+--------------+---------+--------+
|libuv     |libuv  |All         |CPython and |2    |CFFI          |Optional;|Default;|
|          |       |interpreters|PyPy        |years|              |default  |optional|
|          |       |on Windows  |            |     |              |         |        |
+----------+-------+------------+------------+-----+--------------+---------+--------+

.. _libev-impl:

libev
-----

`libev`_ is a venerable event loop library that has been the default
in gevent since 1.0a1 in 2011 when it replaced libevent. libev has
existed since 2007.

.. note::

   In the future, this Cython implementation may be deprecated to be
   replaced with :ref:`libev-cffi`.

.. _libev-dev:

.. rubric:: Development and Source

libev is a stable library and does not change quickly. Changes are
accepted in the form of patches emailed to a mailing list. Due to its
age and its portability requirements, it makes heavy use of
preprocessor macros, which some may find hinders readability of the
source code.

.. _libev-plat:

.. rubric:: Platform Support

gevent tests libev on Linux and macOS. There is no known list of
platforms officially supported by libev, although FreeBSD, OpenBSD and
Solaris/SmartOS have been reported to work with gevent on libev at
various points.

On Windows, libev has `many limitations
<http://pod.tst.eu/http://cvs.schmorp.de/libev/ev.pod#WIN32_PLATFORM_LIMITATIONS_AND_WORKA>`_.
gevent relies on the Microsoft C runtime functions to map from Windows
socket handles to integer file descriptors for libev using a somewhat
complex mapping; this prevents the CFFI implementation from being
used (which in turn prevents PyPy from using libev on Windows).

There is no known public CI infrastructure for libev itself.

.. _libev-cffi:

libev-cffi
----------

This uses libev exactly as above, but instead of using Cython it uses
CFFI. That makes it suitable (and the default) for PyPy. It can also
make it easier to debug, since more details are preserved for
tracebacks.


.. note::

   In the future, this CFFI implementation may become the default and replace
   :ref:`libev-impl`.

.. rubric:: When To Use

On PyPy or when debugging.


libuv
-----

libuv is an event loop library developed since 2011 for the use of
node 0.5. It was originally a wrapper around libev on non-Windows
platforms and directly used the native Windows IOCP support on Windows
(this code was contributed by Microsoft). Now it has its own loop
implementation on all supported platforms.

libuv provides libev-like `"poll handles"
<http://docs.libuv.org/en/v1.x/poll.html>`_, and in gevent 1.3 that is
what gevent uses for IO. But libuv also provides higher-level
abstractions around read and write requests that may offer improved
performance. In the future, gevent might use those abstractions.

.. note::

   In the future, this implementation may become the default on all
   platforms.

.. rubric:: Development and Source

libuv is developed by the libuv organization on `github
<https://github.com/libuv/libuv>`_. It has a large, active community
and is used in many popular projects including node.js.

The source code is written in a clean and consistent coding style,
potentially making it easier to read and debug.

.. rubric:: Platform Support

gevent tests libuv on Linux, Windows and macOS. libuv publishes an
extensive list of `supported platforms
<https://github.com/libuv/libuv/blob/v1.x/SUPPORTED_PLATFORMS.md>`_
that are likely to work with gevent. libuv `maintains a public CI
infrastructure <https://ci.nodejs.org/view/libuv/>`_.

.. rubric:: When To Use libuv


- You want to use PyPy on Windows.
- You want to develop on Windows (Windows is not recommended for
  production).
- You want to use an operating system not supported by libev such as
  IBM i.

  .. note::

     Platforms other than Linux, macOS and Windows are not
     tested by gevent.

.. _libuv-limits:

Limitations and Differences
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Because of its newness, and because of some design decisions inherent
in the library and the ecosystem, there are some limitations and
differences in the way gevent behaves using libuv compared to libev.

- Timers (such as ``gevent.sleep`` and ``gevent.Timeout``) only
  support a resolution of 1ms (in practice, it's closer to 1.5ms).
  Attempting to use something smaller will automatically increase it
  to 1ms and issue a warning. Because libuv only supports millisecond
  resolution by rounding a higher-precision clock to an integer number
  of milliseconds, timers apparently suffer from more jitter.

- Using negative timeouts may behave differently from libev.

- libuv blocks delivery of all signals, so signals are handled using
  an (arbitrary) 0.3 second timer. This means that signal handling
  will be delayed by up to that amount, and that the longest the
  event loop can sleep in the operating system's ``poll`` call is
  that amount. Note that this is what gevent does for libev on
  Windows too.

- libuv only supports one io watcher per file descriptor, whereas
  libev and gevent have always supported many watchers using
  different settings. The libev behaviour is emulated at the Python
  level.

- Looping multiple times and expecting events for the same file
  descriptor to be raised each time without any data being read or
  written (as works with libev) does not appear to work correctly on
  Linux when using ``gevent.select.poll`` or a monkey-patched
  ``selectors.PollSelector``.

- If anything unexpected happens, libuv likes to ``abort()`` the
  entire process instead of reporting an error. For example, closing
  a file descriptor it is using in a watcher may cause the entire
  process to be exited.

- The order in which timers and other callbacks are invoked may be
  different than in libev. In particular, timers and IO callbacks
  happen in a different order, and timers may easily be off by up to
  half of the nominal 1ms resolution. See :issue:`1057`.

- There is no support for priorities within classes of watchers. libev
  has some support for priorities and this is exposed in the low-level
  gevent API, but it was never documented.

- Low-level ``fork`` and ``child`` watchers are not available. gevent
  emulates these in Python on platforms that supply :func:`os.fork`.
  Child watchers use ``SIGCHLD``, just as on libev, so the same
  caveats apply.

- Low-level ``prepare`` watchers are not available. gevent uses
  prepare watchers for internal purposes. If necessary, this could be
  emulated in Python.

Performance
===========

In the various micro-benchmarks gevent has, performance among all three
loop implementations is roughly the same. There doesn't seem to be a
clear winner or loser.

.. _libev: http://software.schmorp.de/pkg/libev.html
.. _libuv: http://libuv.org

..  LocalWords:  gevent libev cffi PyPy CFFI libuv FreeBSD CPython Cython
