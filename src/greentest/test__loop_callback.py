from gevent.core import loop

count = 0


def incr():
    global count
    count += 1

loop = loop()
loop.run_callback(incr)
loop.run()
assert count == 1, count
