"""Testing that greenlet restores sys.exc_info.

Passes with CPython + greenlet 0.4.0

Fails with PyPy 2.2.1
"""
from __future__ import print_function
import sys
import greenlet


print('Your greenlet version: %s' % (getattr(greenlet, '__version__', None), ))


result = []


def func():
    result.append(repr(sys.exc_info()))


g = greenlet.greenlet(func)
try:
    1 / 0
except ZeroDivisionError:
    g.switch()


assert result == ['(None, None, None)'], result
