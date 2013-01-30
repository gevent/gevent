import gevent

# Loop of initial Hub is default loop.
hub = gevent.get_hub()
assert hub.loop.default, hub

# Save `gevent.core.loop` object for later comparison.
initloop = hub.loop

# Increase test complexity via threadpool creation.
# Implicitly creates fork watcher connected to the current event loop.
tp = hub.threadpool

# Destroy hub. Does not destroy libev default loop if not explicitly told to.
hub.destroy()

# Create new hub. Must re-use existing libev default loop.
hub = gevent.get_hub()
assert hub.loop.default, hub

# Ensure that loop object is identical to the initial one.
assert hub.loop is initloop

# Destroy hub including default loop.
hub.destroy(destroy_loop=True)

# Create new hub and explicitly request creation of a new default loop.
hub = gevent.get_hub(default=True)
assert hub.loop.default, hub

# `gevent.core.loop` objects as well as libev loop pointers must differ.
assert hub.loop is not initloop
assert hub.loop.ptr != initloop.ptr

# Destroy hub including default loop, create new hub with non-default loop.
hub.destroy(destroy_loop=True)
hub = gevent.get_hub()
assert not hub.loop.default, hub

hub.destroy()
