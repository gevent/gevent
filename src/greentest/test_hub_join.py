import gevent

# hub.join() guarantees that loop has exited cleanly
res = gevent.get_hub().join()
assert res is True, res
res = gevent.get_hub().join()
assert res is True, res

# but it is still possible to use gevent afterwards
gevent.sleep(0.01)

res = gevent.get_hub().join()
assert res is True, res
