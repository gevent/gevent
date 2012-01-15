import gevent
hub = gevent.get_hub()
assert hub.loop.default, hub
hub.destroy()

hub = gevent.get_hub()
assert hub.loop.default, hub
hub.destroy(destroy_loop=True)

hub = gevent.get_hub()
assert not hub.loop.default, hub
hub.destroy()
