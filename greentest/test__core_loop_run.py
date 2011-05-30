import sys
from gevent import core, signal
loop = core.loop()


signal = signal(2, sys.stderr.write, 'INTERRUPT!')

print ('must exit immediatelly...')
loop.run()  # must exit immediatelly
print ('...and once more...')
loop.run()  # repeating does not fail
print ('..done')

print ('must exit after 0.5 seconds.')
timer = loop.timer(0.5)
timer.start(lambda: None)
loop.run()

del loop
