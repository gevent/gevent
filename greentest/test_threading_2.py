# testing gevent's Event, Lock, RLock, Semaphore, BoundedSemaphore with standard test_threading
from __future__ import print_function
from six import xrange

setup_ = '''from gevent import monkey; monkey.patch_all()
from gevent.event import Event
from gevent.lock import RLock, Semaphore, BoundedSemaphore
from gevent.thread import allocate_lock as Lock
import threading
threading.Event = Event
threading.Lock = Lock
threading.RLock = RLock
threading.Semaphore = Semaphore
threading.BoundedSemaphore = BoundedSemaphore
if not hasattr(threading, 'current_thread'):
    threading.current_thread = threading.currentThread
if not hasattr(threading.Thread, 'name'):
    threading.Thread.name = property(lambda self: self.getName())
if not hasattr(threading.Thread, 'is_alive'):
    threading.Thread.is_alive = threading.Thread.isAlive
if not hasattr(threading.Thread, 'daemon'):
    threading.Thread.daemon = property(threading.Thread.isDaemon, threading.Thread.setDaemon)
'''

exec(setup_)

setup_3 = '\n'.join('            %s' % line for line in setup_.split('\n'))
setup_4 = '\n'.join('                %s' % line for line in setup_.split('\n'))
setup_5 = '\n'.join('                    %s' % line for line in setup_.split('\n'))


try:
    from test import support
    from test.support import verbose
except ImportError:
    from test import test_support as support
    from test.test_support import verbose
import random
import re
import sys
import threading
try:
    import thread
except ImportError:
    import _thread as thread
import time
import unittest
import weakref

import lock_tests

# A trivial mutable counter.


class Counter(object):
    def __init__(self):
        self.value = 0

    def inc(self):
        self.value += 1

    def dec(self):
        self.value -= 1

    def get(self):
        return self.value


class TestThread(threading.Thread):
    def __init__(self, name, testcase, sema, mutex, nrunning):
        threading.Thread.__init__(self, name=name)
        self.testcase = testcase
        self.sema = sema
        self.mutex = mutex
        self.nrunning = nrunning

    def run(self):
        delay = random.random() / 10000.0
        if verbose:
            print('task %s will run for %.1f usec' % (
                self.name, delay * 1e6))

        with self.sema:
            with self.mutex:
                self.nrunning.inc()
                if verbose:
                    print(self.nrunning.get(), 'tasks are running')
                self.testcase.assert_(self.nrunning.get() <= 3)

            time.sleep(delay)
            if verbose:
                print('task', self.name, 'done')

            with self.mutex:
                self.nrunning.dec()
                self.testcase.assert_(self.nrunning.get() >= 0)
                if verbose:
                    print('%s is finished. %d tasks are running' % (
                        self.name, self.nrunning.get()))


class ThreadTests(unittest.TestCase):

    # Create a bunch of threads, let each do some work, wait until all are
    # done.
    def test_various_ops(self):
        # This takes about n/3 seconds to run (about n/3 clumps of tasks,
        # times about 1 second per clump).
        NUMTASKS = 10

        # no more than 3 of the 10 can run at once
        sema = threading.BoundedSemaphore(value=3)
        mutex = threading.RLock()
        numrunning = Counter()

        threads = []

        for i in range(NUMTASKS):
            t = TestThread("<thread %d>" % i, self, sema, mutex, numrunning)
            threads.append(t)
            if hasattr(t, 'ident'):
                self.failUnlessEqual(t.ident, None)
                self.assert_(re.match('<TestThread\(.*, initial\)>', repr(t)))
            t.start()

        if verbose:
            print('waiting for all tasks to complete')
        for t in threads:
            t.join(NUMTASKS)
            self.assert_(not t.is_alive())
            if hasattr(t, 'ident'):
                self.failIfEqual(t.ident, 0)
                self.assertFalse(t.ident is None)
                self.assert_(re.match('<TestThread\(.*, \w+ -?\d+\)>', repr(t)))
        if verbose:
            print('all tasks done')
        self.assertEqual(numrunning.get(), 0)

    if sys.version_info[:2] > (2, 5):
        def test_ident_of_no_threading_threads(self):
            # The ident still must work for the main thread and dummy threads.
            self.assertFalse(threading.currentThread().ident is None)

            def f():
                ident.append(threading.currentThread().ident)
                done.set()
            done = threading.Event()
            ident = []
            thread.start_new_thread(f, ())
            done.wait()
            self.assertFalse(ident[0] is None)
            # Kill the "immortal" _DummyThread
            del threading._active[ident[0]]

    # run with a small(ish) thread stack size (256kB)
    def test_various_ops_small_stack(self):
        if verbose:
            print('with 256kB thread stack size...')
        try:
            threading.stack_size(262144)
        except thread.error:
            if verbose:
                print('platform does not support changing thread stack size')
            return
        self.test_various_ops()
        threading.stack_size(0)

    # run with a large thread stack size (1MB)
    def test_various_ops_large_stack(self):
        if verbose:
            print('with 1MB thread stack size...')
        try:
            threading.stack_size(0x100000)
        except thread.error:
            if verbose:
                print('platform does not support changing thread stack size')
            return
        self.test_various_ops()
        threading.stack_size(0)

    def test_foreign_thread(self):
        # Check that a "foreign" thread can use the threading module.
        def f(mutex):
            # Calling current_thread() forces an entry for the foreign
            # thread to get made in the threading._active map.
            threading.current_thread()
            mutex.release()

        mutex = threading.Lock()
        mutex.acquire()
        tid = thread.start_new_thread(f, (mutex,))
        # Wait for the thread to finish.
        mutex.acquire()
        self.assert_(tid in threading._active)
        self.assert_(isinstance(threading._active[tid],
                                threading._DummyThread))
        del threading._active[tid]
        # in gevent, we actually clean up threading._active, but it's not happended there yet

    # PyThreadState_SetAsyncExc() is a CPython-only gimmick, not (currently)
    # exposed at the Python level.  This test relies on ctypes to get at it.
    def SKIP_test_PyThreadState_SetAsyncExc(self):
        try:
            import ctypes
        except ImportError:
            if verbose:
                print("test_PyThreadState_SetAsyncExc can't import ctypes")
            return  # can't do anything

        set_async_exc = ctypes.pythonapi.PyThreadState_SetAsyncExc

        class AsyncExc(Exception):
            pass

        exception = ctypes.py_object(AsyncExc)

        # `worker_started` is set by the thread when it's inside a try/except
        # block waiting to catch the asynchronously set AsyncExc exception.
        # `worker_saw_exception` is set by the thread upon catching that
        # exception.
        worker_started = threading.Event()
        worker_saw_exception = threading.Event()

        class Worker(threading.Thread):
            def run(self):
                self.id = thread.get_ident()
                self.finished = False

                try:
                    while True:
                        worker_started.set()
                        time.sleep(0.1)
                except AsyncExc:
                    self.finished = True
                    worker_saw_exception.set()

        t = Worker()
        t.daemon = True  # so if this fails, we don't hang Python at shutdown
        t.start()
        if verbose:
            print("    started worker thread")

        # Try a thread id that doesn't make sense.
        if verbose:
            print("    trying nonsensical thread id")
        result = set_async_exc(ctypes.c_long(-1), exception)
        self.assertEqual(result, 0)  # no thread states modified

        # Now raise an exception in the worker thread.
        if verbose:
            print("    waiting for worker thread to get started")
        worker_started.wait()
        if verbose:
            print("    verifying worker hasn't exited")
        self.assert_(not t.finished)
        if verbose:
            print("    attempting to raise asynch exception in worker")
        result = set_async_exc(ctypes.c_long(t.id), exception)
        self.assertEqual(result, 1)  # one thread state modified
        if verbose:
            print("    waiting for worker to say it caught the exception")
        worker_saw_exception.wait(timeout=10)
        self.assert_(t.finished)
        if verbose:
            print("    all OK -- joining worker")
        if t.finished:
            t.join()
        # else the thread is still running, and we have no way to kill it

    if sys.version_info[:2] > (2, 5):
        def test_limbo_cleanup(self):
            # Issue 7481: Failure to start thread should cleanup the limbo map.
            def fail_new_thread(*args):
                raise thread.error()
            _start_new_thread = threading._start_new_thread
            threading._start_new_thread = fail_new_thread
            try:
                t = threading.Thread(target=lambda: None)
                self.assertRaises(thread.error, t.start)
                self.assertFalse(
                    t in threading._limbo,
                    "Failed to cleanup _limbo map on failure of Thread.start().")
            finally:
                threading._start_new_thread = _start_new_thread

    if sys.version_info[:2] > (2, 5):
        def test_finalize_runnning_thread(self):
            # Issue 1402: the PyGILState_Ensure / _Release functions may be called
            # very late on python exit: on deallocation of a running thread for
            # example.
            try:
                import ctypes
            except ImportError:
                if verbose:
                    print("test_finalize_with_runnning_thread can't import ctypes")
                return  # can't do anything

            del ctypes  # pyflakes fix

            import subprocess
            rc = subprocess.call([sys.executable, "-c", """if 1:
%s
                import ctypes, sys, time
                try:
                    import thread
                except ImportError:
                    import _thread as thread

                # This lock is used as a simple event variable.
                ready = thread.allocate_lock()
                ready.acquire()

                # Module globals are cleared before __del__ is run
                # So we save the functions in class dict
                class C:
                    ensure = ctypes.pythonapi.PyGILState_Ensure
                    release = ctypes.pythonapi.PyGILState_Release
                    def __del__(self):
                        state = self.ensure()
                        self.release(state)

                def waitingThread():
                    x = C()
                    ready.release()
                    time.sleep(100)

                thread.start_new_thread(waitingThread, ())
                ready.acquire()  # Be sure the other thread is waiting.
                sys.exit(42)
                """ % setup_4])
            self.assertEqual(rc, 42)

    if sys.version_info[:2] > (2, 5):
        def test_join_nondaemon_on_shutdown(self):
            # Issue 1722344
            # Raising SystemExit skipped threading._shutdown
            import subprocess
            p = subprocess.Popen([sys.executable, "-c", """if 1:
%s
                    import threading
                    from time import sleep

                    def child():
                        sleep(1)
                        # As a non-daemon thread we SHOULD wake up and nothing
                        # should be torn down yet
                        print("Woke up, sleep function is: %%r" %% sleep)

                    threading.Thread(target=child).start()
                    raise SystemExit
                """ % setup_5],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            stdout = stdout.strip()
            assert re.match(b'^Woke up, sleep function is: <.*?sleep.*?>$', stdout), repr(stdout)
            stderr = re.sub(br"^\[\d+ refs\]", b"", stderr, re.MULTILINE).strip()
            self.assertEqual(stderr, b"")

    def test_enumerate_after_join(self):
        # Try hard to trigger #1703448: a thread is still returned in
        # threading.enumerate() after it has been join()ed.
        enum = threading.enumerate
        old_interval = sys.getcheckinterval()
        try:
            for i in xrange(1, 100):
                # Try a couple times at each thread-switching interval
                # to get more interleavings.
                sys.setcheckinterval(i // 5)
                t = threading.Thread(target=lambda: None)
                t.start()
                t.join()
                l = enum()
                self.assertFalse(t in l,
                    "#1703448 triggered after %d trials: %s" % (i, l))
        finally:
            sys.setcheckinterval(old_interval)

    if sys.version_info[:2] > (2, 5) and not hasattr(sys, 'pypy_version_info'):
        def test_no_refcycle_through_target(self):
            class RunSelfFunction(object):
                def __init__(self, should_raise):
                    # The links in this refcycle from Thread back to self
                    # should be cleaned up when the thread completes.
                    self.should_raise = should_raise
                    self.thread = threading.Thread(target=self._run,
                                                   args=(self,),
                                                   kwargs={'yet_another': self})
                    self.thread.start()

                def _run(self, other_ref, yet_another):
                    if self.should_raise:
                        raise SystemExit

            cyclic_object = RunSelfFunction(should_raise=False)
            weak_cyclic_object = weakref.ref(cyclic_object)
            cyclic_object.thread.join()
            del cyclic_object
            self.assertEquals(None, weak_cyclic_object(),
                              msg=('%d references still around' %
                                   sys.getrefcount(weak_cyclic_object())))

            raising_cyclic_object = RunSelfFunction(should_raise=True)
            weak_raising_cyclic_object = weakref.ref(raising_cyclic_object)
            raising_cyclic_object.thread.join()
            del raising_cyclic_object
            self.assertEquals(None, weak_raising_cyclic_object(),
                              msg=('%d references still around' %
                                   sys.getrefcount(weak_raising_cyclic_object())))


class ThreadJoinOnShutdown(unittest.TestCase):

    def _run_and_join(self, script):
        script = """if 1:
%s
            import sys, os, time, threading

            # a thread, which waits for the main program to terminate
            def joiningfunc(mainthread):
                mainthread.join()
                print('end of thread')
        \n""" % setup_3 + script

        import subprocess
        p = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE)
        rc = p.wait()
        data = p.stdout.read().replace(b'\r', b'')
        self.assertEqual(data, b"end of main\nend of thread\n")
        self.failIf(rc == 2, "interpreter was blocked")
        self.failUnless(rc == 0, "Unexpected error")

    def test_1_join_on_shutdown(self):
        # The usual case: on exit, wait for a non-daemon thread
        script = """if 1:
            import os
            t = threading.Thread(target=joiningfunc,
                                 args=(threading.current_thread(),))
            t.start()
            time.sleep(0.1)
            print('end of main')
            """
        self._run_and_join(script)

    def test_2_join_in_forked_process(self):
        # Like the test above, but from a forked interpreter
        import os
        if not hasattr(os, 'fork'):
            return
        script = """if 1:
            childpid = os.fork()
            if childpid != 0:
                os.waitpid(childpid, 0)
                sys.exit(0)

            t = threading.Thread(target=joiningfunc,
                                 args=(threading.current_thread(),))
            t.start()
            print('end of main')
            """
        self._run_and_join(script)

    def test_3_join_in_forked_from_thread(self):
        # Like the test above, but fork() was called from a worker thread
        # In the forked process, the main Thread object must be marked as stopped.
        import os
        if not hasattr(os, 'fork'):
            return
        # Skip platforms with known problems forking from a worker thread.
        # See http://bugs.python.org/issue3863.
        # skip disable because I think the bug shouldn't apply to gevent -- denis
        #if sys.platform in ('freebsd4', 'freebsd5', 'freebsd6', 'os2emx'):
        #    print(('Skipping test_3_join_in_forked_from_thread'
        #          ' due to known OS bugs on'), sys.platform, file=sys.stderr)
        #    return
        script = """if 1:
            main_thread = threading.current_thread()
            def worker():
                childpid = os.fork()
                if childpid != 0:
                    os.waitpid(childpid, 0)
                    sys.exit(0)

                t = threading.Thread(target=joiningfunc,
                                     args=(main_thread,))
                print('end of main')
                t.start()
                t.join() # Should not block: main_thread is already stopped

            w = threading.Thread(target=worker)
            w.start()
            """
        self._run_and_join(script)


class ThreadingExceptionTests(unittest.TestCase):
    # A RuntimeError should be raised if Thread.start() is called
    # multiple times.
    def test_start_thread_again(self):
        thread = threading.Thread()
        thread.start()
        self.assertRaises(RuntimeError, thread.start)

    def test_joining_current_thread(self):
        current_thread = threading.current_thread()
        self.assertRaises(RuntimeError, current_thread.join)

    def test_joining_inactive_thread(self):
        thread = threading.Thread()
        self.assertRaises(RuntimeError, thread.join)

    def test_daemonize_active_thread(self):
        thread = threading.Thread()
        thread.start()
        self.assertRaises(RuntimeError, setattr, thread, "daemon", True)


class LockTests(lock_tests.LockTests):
    locktype = staticmethod(threading.Lock)


class RLockTests(lock_tests.RLockTests):
    locktype = staticmethod(threading.RLock)


class EventTests(lock_tests.EventTests):
    eventtype = staticmethod(threading.Event)


class ConditionAsRLockTests(lock_tests.RLockTests):
    # An Condition uses an RLock by default and exports its API.
    locktype = staticmethod(threading.Condition)


class ConditionTests(lock_tests.ConditionTests):
    condtype = staticmethod(threading.Condition)


class SemaphoreTests(lock_tests.SemaphoreTests):
    semtype = staticmethod(threading.Semaphore)


class BoundedSemaphoreTests(lock_tests.BoundedSemaphoreTests):
    semtype = staticmethod(threading.BoundedSemaphore)


def main():
    support.run_unittest(LockTests, RLockTests, EventTests,
                         ConditionAsRLockTests, ConditionTests,
                         SemaphoreTests, BoundedSemaphoreTests,
                         ThreadTests,
                         ThreadJoinOnShutdown,
                         ThreadingExceptionTests,
                         )

if __name__ == "__main__":
    main()
