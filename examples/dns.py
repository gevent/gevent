#!/usr/bin/env python

import socket
import gevent
from gevent import core
from gevent.socket import getaddrinfo, getnameinfo
import traceback

def test():
    try:
        print 'gevent socket:'
        print getaddrinfo('www.google.com', 80)
        print getnameinfo(('17.251.200.70', 80), 0)
        print getaddrinfo('fake', 0)
    except socket.gaierror, e:
        traceback.print_exc()

if not core.HAS_EVDNS:
    print "*** WARNING: libevent doesn't have evdns support ***"
gevent.spawn(test).join()

core.dns_shutdown()

print 'stdlib socket:'
try:
    print socket.getaddrinfo('www.google.com', 80)
    print socket.getnameinfo(('17.251.200.70', 80), 0)
    print socket.getaddrinfo('fake', 0)
except socket.gaierror, e:
    traceback.print_exc()
