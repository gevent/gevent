"""Tests that Hub.join() works even when hub is not yet started"""
# rename to test_hub_join()?
import gevent.hub
res = gevent.hub.get_hub().join()
assert res is None, res
assert 'hub' not in gevent.hub._threadlocal.__dict__, gevent.hub._threadlocal.__dict__
