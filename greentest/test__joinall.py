import gevent


def func():
    pass


a = gevent.spawn(func)
b = gevent.spawn(func)
gevent.joinall([a, b, a])
