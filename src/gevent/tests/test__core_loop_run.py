from __future__ import print_function
import sys
# Using a direct import of signal (deprecated).
# We are also called from test__core_loop_run_sig_mod.py,
# which has already done 'import gevent.signal' to be sure we work
# when the module has been imported.
from gevent import core, signal
loop = core.loop(default=False)


signal = signal(2, sys.stderr.write, 'INTERRUPT!')

print('must exit immediately...')
loop.run()  # must exit immediately
print('...and once more...')
loop.run()  # repeating does not fail
print('..done')

print('must exit after 0.5 seconds.')
timer = loop.timer(0.5)
timer.start(lambda: None)
loop.run()
timer.close()
loop.destroy()
del loop
