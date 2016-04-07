from __future__ import print_function
import gevent.monkey; gevent.monkey.patch_all()
import gevent
import os
import multiprocessing

hub = gevent.get_hub()
pid = os.getpid()
newpid = None


def on_fork():
    global newpid
    newpid = os.getpid()

fork_watcher = hub.loop.fork(ref=False)
fork_watcher.start(on_fork)


def run(q):
    # libev only calls fork callbacks at the beginning of
    # the loop; we use callbacks extensively so it takes *two*
    # calls to sleep (with a timer) to actually get wrapped
    # around to the beginning of the loop.
    gevent.sleep(0.01)
    gevent.sleep(0.01)
    q.put(newpid)


def test():
    # Use a thread to make us multi-threaded
    hub.threadpool.apply(lambda: None)
    # If the Queue is global, q.get() hangs on Windows; must pass as
    # an argument.
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=run, args=(q,))
    p.start()
    p.join()
    p_val = q.get()

    assert p_val is not None, "The fork watcher didn't run"
    assert p_val != pid

if __name__ == '__main__':
    # Must call for Windows to fork properly; the fork can't be in the top-level
    multiprocessing.freeze_support()
    # fork watchers weren't firing in multi-threading processes.
    # This test is designed to prove that they are.
    # However, it fails on Windows: The fork watcher never runs!

    test()
