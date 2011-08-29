"""Tests that Hub.join() works even when hub is not yet started"""
# rename to test_hub_join()?
import gevent.hub
res = gevent.hub.get_hub().join()
assert res is True, res
res = gevent.hub.get_hub().join()
assert res is True, res
