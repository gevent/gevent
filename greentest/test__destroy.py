from __future__ import print_function
import gevent
# Loop of initial Hub is default loop.
hub = gevent.get_hub()
assert hub.loop.default, hub

# Destroy hub. Does not destroy default loop if not explicitly told to.
hub.destroy()
hub = gevent.get_hub()
assert hub.loop.default, hub

saved_loop = hub.loop
# Destroy hub including default loop.
hub.destroy(destroy_loop=True)
assert saved_loop.fileno() is None, saved_loop
print(hub, saved_loop)

# Create new hub and explicitly request creation of a new default loop.
hub = gevent.get_hub(default=True)
assert hub.loop.default, hub

# Destroy hub including default loop.
hub.destroy(destroy_loop=True)

# Create new non-default loop in new hub.
hub = gevent.get_hub()
assert not hub.loop.default, hub
hub.destroy()
