from gevent import GreenletExit

assert issubclass(GreenletExit, Exception)
assert not issubclass(GreenletExit, Exception)
