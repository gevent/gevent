import os
import gevent
import six
import sys
from gevent import core
if six.PY3:
    xrange = range


for count in xrange(2):
    for backend in core.supported_backends():
        hub = gevent.get_hub(backend, default=False)
        assert hub.loop.backend == backend, (hub.loop.backend, backend)
        gevent.sleep(0.001)
        fileno = hub.loop.fileno()
        if fileno is not None:
            six.print_('%s. Testing %r: %r' % (count, backend, hub))
            os.close(fileno)
            try:
                gevent.sleep(0.001)
            except SystemError:
                ex = sys.exc_info()[1]
                if '(libev)' in str(ex):
                    six.print_('The error is expected: %s' % ex)
                else:
                    raise
            else:
                raise AssertionError('gevent.sleep() is expected to fail after loop fd was closed')
        else:
            six.print_('%s. %r lacks fileno()' % (count, backend))
        hub.destroy()
        assert 'destroyed' in repr(hub), repr(hub)
