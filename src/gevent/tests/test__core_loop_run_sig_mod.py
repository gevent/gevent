import sys
import gevent.signal
assert gevent.signal # Get gevent.signal as a module, make sure our backwards compatibility kicks in

import test__core_loop_run # this runs main tests, fails if signal() is not callable.
assert test__core_loop_run # pyflakes

from gevent.hub import signal as hub_signal
from gevent import signal as top_signal # pylint:disable=reimported

assert gevent.signal is hub_signal
assert gevent.signal is top_signal
assert hasattr(gevent.signal, 'signal')
s = top_signal(2, sys.stderr.write, 'INTERRUPT')
assert isinstance(s, top_signal)
assert isinstance(s, hub_signal)
