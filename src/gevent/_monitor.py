# Copyright (c) 2018 gevent. See LICENSE for details.
from __future__ import print_function, absolute_import, division

import os
import sys
import traceback

from weakref import ref as wref

from greenlet import settrace
from greenlet import getcurrent

from gevent import config as GEVENT_CONFIG
from gevent.monkey import get_original
from gevent.util import format_run_info
from gevent.events import notify
from gevent.events import EventLoopBlocked
from gevent.events import MemoryUsageThresholdExceeded
from gevent.events import MemoryUsageUnderThreshold
from gevent.events import IPeriodicMonitorThread
from gevent.events import implementer

from gevent._compat import thread_mod_name
from gevent._compat import perf_counter
from gevent._util import gmctime


__all__ = [
    'PeriodicMonitoringThread',
]

get_thread_ident = get_original(thread_mod_name, 'get_ident')
start_new_thread = get_original(thread_mod_name, 'start_new_thread')
thread_sleep = get_original('time', 'sleep')



class MonitorWarning(RuntimeWarning):
    """The type of warnings we emit."""


class GreenletTracer(object):

    # A counter, incremented by the greenlet trace function
    # we install on every greenlet switch. This is reset when the
    # periodic monitoring thread runs.
    greenlet_switch_counter = 0

    # The greenlet last switched to.
    active_greenlet = None

    # The trace function that was previously installed,
    # if any.
    previous_trace_function = None

    def __init__(self):
        prev_trace = settrace(self)
        self.previous_trace_function = prev_trace

    def kill(self): #  pylint:disable=method-hidden
        # Must be called in the monitored thread.
        settrace(self.previous_trace_function)
        self.previous_trace_function = None
        # Become a no-op
        self.kill = lambda: None

    def __call__(self, event, args):
        # This function runs in the thread we are monitoring.
        self.greenlet_switch_counter += 1
        if event in ('switch', 'throw'):
            # args is (origin, target). This is the only defined
            # case
            self.active_greenlet = args[1]
        else:
            self.active_greenlet = None
        if self.previous_trace_function is not None:
            self.previous_trace_function(event, args)

    def did_block_hub(self, hub):
        # Check to see if we have blocked since the last call to this
        # method. Returns a true value if we blocked (not in the hub),
        # a false value if everything is fine.

        # This may be called in the same thread being traced or a
        # different thread; if a different thread, there is a race
        # condition with this being incremented in the thread we're
        # monitoring, but probably not often enough to lead to
        # annoying false positives.

        active_greenlet = self.active_greenlet
        did_switch = self.greenlet_switch_counter != 0
        self.greenlet_switch_counter = 0

        if did_switch or active_greenlet is None or active_greenlet is hub:
            # Either we switched, or nothing is running (we got a
            # trace event we don't know about or were requested to
            # ignore), or we spent the whole time in the hub, blocked
            # for IO. Nothing to report.
            return False
        return True, active_greenlet

    def ignore_current_greenlet_blocking(self):
        # Don't pay attention to the current greenlet.
        self.active_greenlet = None

    def monitor_current_greenlet_blocking(self):
        self.active_greenlet = getcurrent()

    def did_block_hub_report(self, hub, active_greenlet, format_kwargs):
        report = ['=' * 80,
                  '\n%s : Greenlet %s appears to be blocked' %
                  (gmctime(), active_greenlet)]
        report.append("    Reported by %s" % (self,))
        try:
            frame = sys._current_frames()[hub.thread_ident]
        except KeyError:
            # The thread holding the hub has died. Perhaps we shouldn't
            # even report this?
            stack = ["Unknown: No thread found for hub %r\n" % (hub,)]
        else:
            stack = traceback.format_stack(frame)
        report.append('Blocked Stack (for thread id %s):' % (hex(hub.thread_ident),))
        report.append(''.join(stack))
        report.append("Info:")
        report.extend(format_run_info(**format_kwargs))

        return report

class _HubTracer(GreenletTracer):
    def __init__(self, hub, max_blocking_time):
        GreenletTracer.__init__(self)
        self.max_blocking_time = max_blocking_time
        self.hub = hub

    def kill(self): # pylint:disable=method-hidden
        self.hub = None
        GreenletTracer.kill(self)


class HubSwitchTracer(_HubTracer):
    # A greenlet tracer that records the last time we switched *into* the hub.

    last_entered_hub = 0

    def __call__(self, event, args):
        GreenletTracer.__call__(self, event, args)
        if self.active_greenlet is self.hub:
            self.last_entered_hub = perf_counter()

    def did_block_hub(self, hub):
        if perf_counter() - self.last_entered_hub > self.max_blocking_time:
            return True, self.active_greenlet


class MaxSwitchTracer(_HubTracer):
    # A greenlet tracer that records the maximum time between switches,
    # not including time spent in the hub.

    max_blocking = 0

    def __init__(self, hub, max_blocking_time):
        _HubTracer.__init__(self, hub, max_blocking_time)
        self.last_switch = perf_counter()

    def __call__(self, event, args):
        old_active = self.active_greenlet
        GreenletTracer.__call__(self, event, args)
        if old_active is not self.hub and old_active is not None:
            # If we're switching out of the hub, the blocking
            # time doesn't count.
            switched_at = perf_counter()
            self.max_blocking = max(self.max_blocking,
                                    switched_at - self.last_switch)

    def did_block_hub(self, hub):
        if self.max_blocking == 0:
            # We never switched. Check the time now
            self.max_blocking = perf_counter() - self.last_switch

        if self.max_blocking > self.max_blocking_time:
            return True, self.active_greenlet


class _MonitorEntry(object):

    __slots__ = ('function', 'period', 'last_run_time')

    def __init__(self, function, period):
        self.function = function
        self.period = period
        self.last_run_time = 0

    def __eq__(self, other):
        return self.function == other.function and self.period == other.period

    def __repr__(self):
        return repr((self.function, self.period, self.last_run_time))


@implementer(IPeriodicMonitorThread)
class PeriodicMonitoringThread(object):
    # This doesn't extend threading.Thread because that gets monkey-patched.
    # We use the low-level 'start_new_thread' primitive instead.

    # The amount of seconds we will sleep when we think we have nothing
    # to do.
    inactive_sleep_time = 2.0

    # The absolute minimum we will sleep, regardless of
    # what particular monitoring functions want to say.
    min_sleep_time = 0.005

    # The minimum period in seconds at which we will check memory usage.
    # Getting memory usage is fairly expensive.
    min_memory_monitor_period = 2

    # A list of _MonitorEntry objects: [(function(hub), period, last_run_time))]
    # The first entry is always our entry for self.monitor_blocking
    _monitoring_functions = None

    # The calculated min sleep time for the monitoring functions list.
    _calculated_sleep_time = None

    # A boolean value that also happens to capture the
    # memory usage at the time we exceeded the threshold. Reset
    # to 0 when we go back below.
    _memory_exceeded = 0

    # The instance of GreenletTracer we're using
    _greenlet_tracer = None

    def __init__(self, hub):
        self._hub_wref = wref(hub, self._on_hub_gc)
        self.should_run = True

        # Must be installed in the thread that the hub is running in;
        # the trace function is threadlocal
        assert get_thread_ident() == hub.thread_ident
        self._greenlet_tracer = GreenletTracer()

        self._monitoring_functions = [_MonitorEntry(self.monitor_blocking,
                                                    GEVENT_CONFIG.max_blocking_time)]
        self._calculated_sleep_time = GEVENT_CONFIG.max_blocking_time
        # Create the actual monitoring thread. This is effectively a "daemon"
        # thread.
        self.monitor_thread_ident = start_new_thread(self, ())

        # We must track the PID to know if your thread has died after a fork
        self.pid = os.getpid()

    def _on_fork(self):
        # Pseudo-standard method that resolver_ares and threadpool
        # also have, called by hub.reinit()
        pid = os.getpid()
        if pid != self.pid:
            self.pid = pid
            self.monitor_thread_ident = start_new_thread(self, ())

    @property
    def hub(self):
        return self._hub_wref()


    def monitoring_functions(self):
        # Return a list of _MonitorEntry objects

        # Update max_blocking_time each time.
        mbt = GEVENT_CONFIG.max_blocking_time # XXX: Events so we know when this changes.
        if mbt != self._monitoring_functions[0].period:
            self._monitoring_functions[0].period = mbt
            self._calculated_sleep_time = min(x.period for x in self._monitoring_functions)
        return self._monitoring_functions

    def add_monitoring_function(self, function, period):
        if not callable(function):
            raise ValueError("function must be callable")

        if period is None:
            # Remove.
            self._monitoring_functions = [
                x for x in self._monitoring_functions
                if x.function != function
            ]
        elif period <= 0:
            raise ValueError("Period must be positive.")
        else:
            # Add or update period
            entry = _MonitorEntry(function, period)
            self._monitoring_functions = [
                x if x.function != function else entry
                for x in self._monitoring_functions
            ]
            if entry not in self._monitoring_functions:
                self._monitoring_functions.append(entry)
        self._calculated_sleep_time = min(x.period for x in self._monitoring_functions)

    def calculate_sleep_time(self):
        min_sleep = self._calculated_sleep_time
        if min_sleep <= 0:
            # Everyone wants to be disabled. Sleep for a longer period of
            # time than usual so we don't spin unnecessarily. We might be
            # enabled again in the future.
            return self.inactive_sleep_time
        return max((min_sleep, self.min_sleep_time))

    def kill(self):
        if not self.should_run:
            # Prevent overwriting trace functions.
            return
        # Stop this monitoring thread from running.
        self.should_run = False
        # Uninstall our tracing hook
        self._greenlet_tracer.kill()

    def _on_hub_gc(self, _):
        self.kill()

    def __call__(self):
        # The function that runs in the monitoring thread.
        # We cannot use threading.current_thread because it would
        # create an immortal DummyThread object.
        getcurrent().gevent_monitoring_thread = wref(self)

        try:
            while self.should_run:
                functions = self.monitoring_functions()
                assert functions
                sleep_time = self.calculate_sleep_time()

                thread_sleep(sleep_time)

                # Make sure the hub is still around, and still active,
                # and keep it around while we are here.
                hub = self.hub
                if not hub:
                    self.kill()

                if self.should_run:
                    this_run = perf_counter()
                    for entry in functions:
                        f = entry.function
                        period = entry.period
                        last_run = entry.last_run_time
                        if period and last_run + period <= this_run:
                            entry.last_run_time = this_run
                            f(hub)
                del hub # break our reference to hub while we sleep

        except SystemExit:
            pass
        except: # pylint:disable=bare-except
            # We're a daemon thread, so swallow any exceptions that get here
            # during interpreter shutdown.
            if not sys or not sys.stderr: # pragma: no cover
                # Interpreter is shutting down
                pass
            else:
                hub = self.hub
                if hub is not None:
                    # XXX: This tends to do bad things like end the process, because we
                    # try to switch *threads*, which can't happen. Need something better.
                    hub.handle_error(self, *sys.exc_info())

    def monitor_blocking(self, hub):
        # Called periodically to see if the trace function has
        # fired to switch greenlets. If not, we will print
        # the greenlet tree.

        # For tests, we return a true value when we think we found something
        # blocking

        did_block = self._greenlet_tracer.did_block_hub(hub)
        if not did_block:
            return

        active_greenlet = did_block[1]
        report = self._greenlet_tracer.did_block_hub_report(
            hub, active_greenlet,
            dict(greenlet_stacks=False, current_thread_ident=self.monitor_thread_ident))

        stream = hub.exception_stream
        for line in report:
            # Printing line by line may interleave with other things,
            # but it should also prevent a "reentrant call to print"
            # when the report is large.
            print(line, file=stream)

        notify(EventLoopBlocked(active_greenlet, GEVENT_CONFIG.max_blocking_time, report))
        return (active_greenlet, report)

    def ignore_current_greenlet_blocking(self):
        self._greenlet_tracer.ignore_current_greenlet_blocking()

    def monitor_current_greenlet_blocking(self):
        self._greenlet_tracer.monitor_current_greenlet_blocking()

    def _get_process(self): # pylint:disable=method-hidden
        try:
            # The standard library 'resource' module doesn't provide
            # a standard way to get the RSS measure, only the maximum.
            # You might be tempted to try to compute something by adding
            # together text and data sizes, but on many systems those come back
            # zero. So our only option is psutil.
            from psutil import Process, AccessDenied
            # Make sure it works (why would we be denied access to our own process?)
            try:
                proc = Process()
                proc.memory_full_info()
            except AccessDenied: # pragma: no cover
                proc = None
        except ImportError:
            proc = None

        self._get_process = lambda: proc
        return proc

    def can_monitor_memory_usage(self):
        return self._get_process() is not None

    def install_monitor_memory_usage(self):
        # Start monitoring memory usage, if possible.
        # If not possible, emit a warning.
        if not self.can_monitor_memory_usage():
            import warnings
            warnings.warn("Unable to monitor memory usage. Install psutil.",
                          MonitorWarning)
            return

        self.add_monitoring_function(self.monitor_memory_usage,
                                     max(GEVENT_CONFIG.memory_monitor_period,
                                         self.min_memory_monitor_period))

    def monitor_memory_usage(self, _hub):
        max_allowed = GEVENT_CONFIG.max_memory_usage
        if not max_allowed:
            # They disabled it.
            return -1 # value for tests

        rusage = self._get_process().memory_full_info()
        # uss only documented available on Windows, Linux, and OS X.
        # If not available, fall back to rss as an aproximation.
        mem_usage = getattr(rusage, 'uss', 0) or rusage.rss

        event = None # Return value for tests

        if mem_usage > max_allowed:
            if mem_usage > self._memory_exceeded:
                # We're still growing
                event = MemoryUsageThresholdExceeded(
                    mem_usage, max_allowed, rusage)
                notify(event)
            self._memory_exceeded = mem_usage
        else:
            # we're below. Were we above it last time?
            if self._memory_exceeded:
                event = MemoryUsageUnderThreshold(
                    mem_usage, max_allowed, rusage, self._memory_exceeded)
                notify(event)
            self._memory_exceeded = 0

        return event

    def __repr__(self):
        return '<%s at %s in thread %s greenlet %r for %r>' % (
            self.__class__.__name__,
            hex(id(self)),
            hex(self.monitor_thread_ident),
            getcurrent(),
            self._hub_wref())
