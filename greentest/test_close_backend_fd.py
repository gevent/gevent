import os
import traceback
import gevent


for _ in xrange(2):
    for backend in gevent.core.supported_backends():
        print 'Testing backend: %r' % backend
        hub = gevent.get_hub(backend)
        print hub
        assert hub.loop.backend == backend, (hub.loop.backend, backend)
        gevent.sleep(0.001)
        fd = getattr(hub.loop, 'backend_fd', None)
        if fd is not None and fd >= 0:
            os.close(hub.loop.backend_fd)
            try:
                gevent.sleep(0.001)
            except SystemError, ex:
                if '(libev)' not in str(ex):
                    raise
                traceback.print_exc()
        else:
            print 'Skipping %r' % backend
        hub.destroy()
        print
