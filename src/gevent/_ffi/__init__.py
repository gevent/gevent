"""
Internal helpers for FFI implementations.
"""
from __future__ import print_function, absolute_import

import os
import sys

def _dbg(*args, **kwargs):
    # pylint:disable=unused-argument
    pass

#_dbg = print

def _pid_dbg(*args, **kwargs):
    kwargs['file'] = sys.stderr
    print(os.getpid(), *args, **kwargs)

GEVENT_DEBUG = 0
CRITICAL = 1
ERROR = 3
DEBUG = 5
TRACE = 9

if os.getenv("GEVENT_DEBUG") == 'critical':
    GEVENT_DEBUG = CRITICAL
elif os.getenv("GEVENT_DEBUG") == 'error':
    GEVENT_DEBUG = ERROR
elif os.getenv('GEVENT_DEBUG') == 'debug':
    GEVENT_DEBUG = DEBUG
elif os.getenv('GEVENT_DEBUG') == 'trace':
    _dbg = _pid_dbg
    GEVENT_DEBUG = TRACE
