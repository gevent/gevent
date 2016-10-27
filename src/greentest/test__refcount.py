# Copyright (c) 2008 AG Projects
# Author: Denis Bilenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""This test checks that underlying socket instances (gevent.socket.socket._sock)
are not leaked by the hub.
"""
from __future__ import print_function
from _socket import socket
import sys
if sys.version_info[0] >= 3:
    # Python3 enforces that __weakref__ appears only once,
    # and not when a slotted class inherits from an unslotted class.
    # We mess around with the class MRO below and violate that rule
    # (because socket.socket defines __slots__ with __weakref__),
    # so import socket.socket before that can happen.
    __import__('socket')
    Socket = socket
else:
    class Socket(socket):
        "Something we can have a weakref to"

import _socket
_socket.socket = Socket

import greentest
from gevent import monkey; monkey.patch_all()

from pprint import pformat
try:
    from thread import start_new_thread
except ImportError:
    from _thread import start_new_thread
from time import sleep
import weakref
import gc

import socket
socket._realsocket = Socket

SOCKET_TIMEOUT = 0.1
if greentest.RUNNING_ON_CI:
    SOCKET_TIMEOUT *= 2

def init_server():
    s = socket.socket()
    s.settimeout(SOCKET_TIMEOUT)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', 0))
    s.listen(5)
    return s


def handle_request(s, raise_on_timeout):
    try:
        conn, address = s.accept()
    except socket.timeout:
        if raise_on_timeout:
            raise
        else:
            return
    #print('handle_request - accepted')
    res = conn.recv(100)
    assert res == b'hello', repr(res)
    #print('handle_request - recvd %r' % res)
    res = conn.send(b'bye')
    #print('handle_request - sent %r' % res)
    #print('handle_request - conn refcount: %s' % sys.getrefcount(conn))
    #conn.close()


def make_request(port):
    #print('make_request')
    s = socket.socket()
    s.connect(('127.0.0.1', port))
    #print('make_request - connected')
    res = s.send(b'hello')
    #print('make_request - sent %s' % res)
    res = s.recv(100)
    assert res == b'bye', repr(res)
    #print('make_request - recvd %r' % res)
    #s.close()


def run_interaction(run_client):
    s = init_server()
    start_new_thread(handle_request, (s, run_client))
    if run_client:
        port = s.getsockname()[1]
        start_new_thread(make_request, (port, ))
    sleep(0.1 + SOCKET_TIMEOUT)
    #print(sys.getrefcount(s._sock))
    #s.close()
    w = weakref.ref(s._sock)
    s.close()
    if greentest.RUNNING_ON_APPVEYOR:
        # The background thread may not have even had a chance to run
        # yet, sleep again to be sure it does. Otherwise there could be
        # strong refs to the socket still around.
        try:
            sleep(0.1 + SOCKET_TIMEOUT)
        except Exception:
            pass

    return w


def run_and_check(run_client):
    w = run_interaction(run_client=run_client)
    if greentest.PYPY:
        # PyPy doesn't use a strict ref counting and must
        # run a gc, but the object should be gone
        gc.collect()
    if w():
        print(pformat(gc.get_referrers(w())))
        for x in gc.get_referrers(w()):
            print(pformat(x))
            for y in gc.get_referrers(x):
                print('-', pformat(y))
        raise AssertionError('server should be dead by now')


@greentest.skipOnAppVeyor("Often fail with timeouts; not sure why.")
@greentest.skipOnPyPy3OnCI("Often fails with timeouts; not sure why.")
class Test(greentest.TestCase):

    __timeout__ = 10

    def test_clean_exit(self):
        run_and_check(True)
        run_and_check(True)

    def test_timeout_exit(self):
        run_and_check(False)
        run_and_check(False)


if __name__ == '__main__':
    greentest.main()
