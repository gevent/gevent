"""A few utilities for raw greenlets"""

import traceback
from gevent import core
from gevent.hub import greenlet, get_hub, GreenletExit, Waiter, sleep


__all__ = ['spawn',
           'spawn_later',
           'kill',
           'killall',
           'join',
           'joinall']


def _switch_helper(function, args, kwargs):
    # work around the fact that greenlet.switch does not support keyword args
    return function(*args, **kwargs)


def spawn(function, *args, **kwargs):
    if kwargs:
        g = greenlet(_switch_helper, get_hub())
        core.active_event(g.switch, function, args, kwargs)
        return g
    else:
        g = greenlet(function, get_hub())
        core.active_event(g.switch, *args)
        return g


def spawn_later(seconds, function, *args, **kwargs):
    if kwargs:
        g = greenlet(_switch_helper, get_hub())
        core.timer(seconds, g.switch, function, args, kwargs)
        return g
    else:
        g = greenlet(function, get_hub())
        core.timer(seconds, g.switch, *args)
        return g


def _kill(greenlet, exception, waiter):
    try:
        greenlet.throw(exception)
    except:
        traceback.print_exc()
    waiter.switch()


def kill(greenlet, exception=GreenletExit, block=False, polling_period=0.2):
    """Kill greenlet with exception (GreenletExit by default).
    Wait for it to die if block is true.
    """
    if not greenlet.dead:
        waiter = Waiter()
        core.active_event(_kill, greenlet, exception, waiter)
        if block:
            waiter.wait()
            join(greenlet, polling_period=polling_period)


def _killall(greenlets, exception, waiter):
    diehards = []
    for g in greenlets:
        if not g.dead:
            try:
                g.throw(exception)
            except:
                traceback.print_exc()
            if not g.dead:
                diehards.append(g)
    waiter.switch(diehards)


def killall(greenlets, exception=GreenletExit, block=False, polling_period=0.2):
    """Kill all the greenlets with exception (GreenletExit by default).
    Wait for them to die if block is true.
    """
    waiter = Waiter()
    core.active_event(_killall, greenlets, exception, waiter)
    if block:
        alive = waiter.wait()
        if alive:
            joinall(alive, polling_period=polling_period)


def join(greenlet, polling_period=0.2):
    """Wait for a greenlet to finish by polling its status"""
    delay = 0.002
    while not greenlet.dead:
        delay = min(polling_period, delay*2)
        sleep(delay)


def joinall(greenlets, polling_period=0.2):
    """Wait for the greenlets to finish by polling their status"""
    current = 0
    while current < len(greenlets) and greenlets[current].dead:
        current += 1
    delay = 0.002
    while current < len(greenlets):
        delay = min(polling_period, delay*2)
        sleep(delay)
        while current < len(greenlets) and greenlets[current].dead:
            current += 1

