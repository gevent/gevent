import sys
import gevent
from gevent.resolver_ares import Resolver
from gevent import socket
print gevent.__file__

address = ('127.0.0.10', 53)
listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    listener.bind(address)
except socket.error, ex:
    if 'permission denied' in str(ex).lower():
        sys.stderr.write('This test binds on port 53 and thus must be run as root.\n')
        sys.exit(0)
    raise


def reader():
    while True:
        print listener.recvfrom(10000)

gevent.spawn(reader)

r = gevent.get_hub().resolver = Resolver(servers=['127.0.0.10'], timeout=0.001, tries=1)
try:
    result = r.gethostbyname('www.google.com')
except socket.gaierror, ex:
    if 'ARES_ETIMEOUT' not in str(ex):
        raise
else:
    raise AssertionError('Expected timeout, got %r' % (result, ))
