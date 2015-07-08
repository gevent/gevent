from __future__ import print_function
import gevent.monkey; gevent.monkey.patch_all()
import gevent
import os

hub = gevent.get_hub()
pid = os.getpid()
newpid = None


def on_fork():
    global newpid
    newpid = os.getpid()

fork_watcher = hub.loop.fork(ref=False)
fork_watcher.start(on_fork)

# fork watchers weren't firing in multi-threading processes.


def run():
    # libev only calls fork callbacks at the beginning of
    # the loop; we use callbacks extensively so it takes *two*
    # calls to sleep (with a timer) to actually get wrapped
    # around to the beginning of the loop.
    gevent.sleep(0.01)
    gevent.sleep(0.01)
    q.put(newpid)


import multiprocessing
# Use a thread to make us multi-threaded
hub.threadpool.apply(lambda: None)

q = multiprocessing.Queue()
p = multiprocessing.Process(target=run)
p.start()
p_val = q.get()
p.join()

assert p_val is not None
assert p_val != pid
