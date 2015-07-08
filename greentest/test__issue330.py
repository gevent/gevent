# A greenlet that's killed before it is ever started
# should never be switched to
import gevent

switched_to = [False, False]


def runner(i):
    switched_to[i] = True


def check(g, g2):
    gevent.joinall((g, g2))
    assert switched_to == [False, False], switched_to

    # They both have a GreenletExit as their value
    assert isinstance(g.value, gevent.GreenletExit)
    assert isinstance(g2.value, gevent.GreenletExit)
    # They both have no reported exc_info
    assert g._exc_info == (None, None, None)
    assert g2._exc_info == (None, None, None)
    assert g._exc_info is not type(g)._exc_info
    assert g2._exc_info is not type(g2)._exc_info

    switched_to[:] = [False, False]

g = gevent.spawn(runner, 0) # create but do not switch to
g2 = gevent.spawn(runner, 1) # create but do not switch to
# Using gevent.kill
gevent.kill(g)
gevent.kill(g2)
check(g, g2)

# killing directly
g = gevent.spawn(runner, 0)
g2 = gevent.spawn(runner, 1)
g.kill()
g2.kill()
check(g, g2)

# throwing
g = gevent.spawn(runner, 0)
g2 = gevent.spawn(runner, 1)
g.throw(gevent.GreenletExit)
g2.throw(gevent.GreenletExit)
check(g, g2)
