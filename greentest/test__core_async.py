from __future__ import with_statement
import gevent
import gevent.core
import time
import thread


hub = gevent.get_hub()
watcher = hub.loop.async()

gevent.spawn_later(0.1, thread.start_new_thread, watcher.send, ())

start = time.time()

with gevent.Timeout(0.3):
    hub.wait(watcher)

print 'Watcher %r reacted after %.6f seconds' % (watcher, time.time() - start - 0.1)
