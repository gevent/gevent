import os
import traceback
import gevent


for _ in xrange(2):
    for backend in gevent.core.supported_backends():
        hub = gevent.get_hub(backend)
        assert hub.loop.backend == backend, (hub.loop.backend, backend)
        gevent.sleep(0.001)
        fileno = hub.loop.fileno()
        if fileno is not None:
            print 'Testing %r: %r' % (backend, hub)
            os.close(fileno)
            try:
                gevent.sleep(0.001)
            except SystemError, ex:
                if '(libev)' in str(ex):
                    print 'The error is expected: %s' % ex
                else:
                    raise
            else:
                raise AssertionError('gevent.sleep() is expected to fail after loop fd was closed')
        else:
            print 'Skipping %r' % backend
        hub.destroy()
