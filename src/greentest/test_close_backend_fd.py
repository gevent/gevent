from __future__ import print_function
import os
import gevent
from gevent import core


if getattr(core, 'LIBEV_EMBED', False):
    # hub.loop.fileno is only defined when
    # we embed libev for some reason.
    # Choosing specific backends is also only supported by libev
    # (not libuv), and besides, libuv has a nasty tendency to
    # abort() the process if its FD gets closed.

    for count in range(2):
        for backend in core.supported_backends():
            hub = gevent.get_hub(backend, default=False)
            assert hub.loop.backend == backend, (hub.loop.backend, backend)
            gevent.sleep(0.001)
            fileno = hub.loop.fileno()
            if fileno is not None:
                print('%s. Testing %r: %r' % (count, backend, hub))
                os.close(fileno)
                try:
                    gevent.sleep(0.001)
                except SystemError as ex:
                    if '(libev)' in str(ex):
                        print('The error is expected: %s' % ex)
                    else:
                        raise
                else:
                    raise AssertionError('gevent.sleep() is expected to fail after loop fd was closed')
            else:
                print('%s. %r lacks fileno()' % (count, backend))
            hub.destroy()
            assert 'destroyed' in repr(hub), repr(hub)
