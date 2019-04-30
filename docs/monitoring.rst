==============================================
 Monitoring and Debugging gevent Applications
==============================================

gevent applications are often long-running server processes. Beginning
with version 1.3, gevent has special support for monitoring such
applications and getting visibility into them.

.. tip::

   For some additional tools, see the comments on `issue 1021
   <https://github.com/gevent/gevent/issues/1021>`_.

The Monitor Thread
==================

gevent can be :attr:`configured
<gevent._config.Config.monitor_thread>` to start a native thread to
watch over each hub it creates. Out of the box, that thread has
support to watch two things, but you can :func:`add your own functions
<gevent.events.IPeriodicMonitorThread.add_monitoring_function>` to be
called periodically in this thread.

Blocking
--------

When the monitor thread is enabled, by default it will watch for
greenlets that block the event loop for longer than a
:attr:`configurable <gevent._config.Config.max_blocking_time>` time
interval. When such a blocking greenlet is detected, it will print
:func:`a report <gevent.util.format_run_info>` to the hub's
:attr:`~gevent.hub.Hub.exception_stream`. It will also emit the
:class:`gevent.events.EventLoopBlocked` event.

.. seealso:: :func:`gevent.util.assert_switches`

   For a scoped version of this.

Memory Usage
------------

Optionally, you can set a :attr:`memory limit
<gevent._config.Config.max_memory_usage>`. The monitor thread will
check the process's memory usage every
:attr:`~gevent._config.Config.memory_monitor_period` seconds, and if
it is found to exceed this value, the
:class:`gevent.events.MemoryUsageThresholdExceeded` event will be
emitted. If in the future memory usage declines below the configured
value, the :class:`gevent.events.MemoryUsageUnderThreshold` event will
be emitted.

.. important::

   `psutil <https://pypi.org/project/psutil>`_ must be
   installed to monitor memory usage.

Visibility
==========

.. tip::

   Insight into the monkey-patching process can be obtained by
   observing the events :mod:`gevent.monkey` emits.

It is sometimes useful to get an overview of all existing greenlets
and their stack traces. The function
:func:`gevent.util.print_run_info` will collect this info and print it
(:func:`gevent.util.format_run_info` only collects and returns this
information). The greenlets are organized into a tree based on the
greenlet that spawned them.

The ``print_run_info`` function is commonly hooked up to a signal
handler to get the application state at any given time.

For each greenlet the following information is printed:

- Its current execution stack
- If it is not running, its termination status and
  :attr:`gevent.Greenlet.value` or
  :attr:`gevent.Greenlet.exception`
- The :attr:`stack at which it was spawned
  <gevent.Greenlet.spawning_stack>`
- Its parent (usually the hub)
- Its :attr:`~gevent.Greenlet.minimal_ident`
- Its :attr:`~gevent.Greenlet.name`
- The :attr:`spawn tree locals <gevent.Greenlet.spawn_tree_locals>`
  (only for the root of the spawn tree).
- The dicts of all :class:`gevent.local.local` objects that are used
  in the greenlet.

The greenlet tree itself is represented as an object that you can also
use for your own purposes: :class:`gevent.util.GreenletTree`.

Profiling
=========

The github repository `nylas/nylas-perftools
<https://github.com/nylas/nylas-perftools>`_ has some
gevent-compatible profilers.

- ``stacksampler`` is a sampling profiler meant to be run in a
  greenlet in your server process and exposes data through an HTTP
  server; it is designed to be suitable for production usage.
- ``py2devtools`` is a greenlet-aware tracing profiler that outputs data
  that can be used by the Chrome dev tools; it is intended for
  developer usage.

..  LocalWords:  greenlets gevent greenlet
