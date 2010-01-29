"""Tests that Hub.shutdown() works even when hub is not yet started"""
import gevent.hub
res = gevent.hub.get_hub().shutdown()
assert res is None, res
