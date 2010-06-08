"""Tests that Hub.shutdown() works even when hub is not yet started"""
import gevent.hub
res = gevent.hub.get_hub().shutdown()
assert res is None, res
assert 'hub' not in gevent.hub._threadlocal.__dict__, gevent.hub._threadlocal.__dict__
