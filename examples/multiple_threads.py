import sys
import gevent
from gevent import monkey


start_new_thread = monkey.get_unpatched('thread', 'start_new_thread')


def _run(func, args, kwargs, async, result):
    try:
        value = func(*args, **kwargs)
        result.append((True, value))
    except:
        result.append((False, sys.exc_info()))
    finally:
        async.send()


def _run_in_thread(func, *args, **kwargs):
    hub = gevent.get_hub()
    async = hub.loop.async()
    result = []
    start_new_thread(_run, (func, args, kwargs, async, result))
    hub.wait(async)
    return result[0]


def run_in_thread(func, *args, **kwargs):
    succeeded, result = _run_in_thread(func, *args, **kwargs)
    if succeeded:
        return result
    else:
        raise result


if __name__ == '__main__':
    import os
    import time
    start = time.time()
    for _ in xrange(4):
        gevent.spawn(run_in_thread, os.system, 'sleep 1')
    gevent.run()
    delay = time.time() - start
    print 'Running "sleep 1" 4 threads. Should take about a second: %.2fs' % delay
