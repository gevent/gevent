#! /usr/bin/env python
"""
Basic socket benchmarks.
"""
from __future__ import print_function, division, absolute_import

import perf

import gevent
from gevent import socket as gsocket

import socket
import threading

def recvall(sock, _):
    while sock.recv(4096):
        pass

N = 10
MB = 1024 * 1024
length = 50 * MB
BIG_DATA = b"x" * length
SMALL_DATA = b'x' * 1000

def _sendto(loops, conn, data, to_send=None):
    addr = ('127.0.0.1', 55678)
    spent_total = 0
    sent = 0
    to_send = len(data) if to_send is None else to_send
    for __ in range(loops):
        for _ in range(N):
            start = perf.perf_counter()
            while sent < to_send:
                sent += conn.sendto(data, 0, addr)
            spent = perf.perf_counter() - start
            spent_total += spent

    return spent_total

def _sendall(loops, conn, data):
    start = perf.perf_counter()
    for __ in range(loops):
        for _ in range(N):
            conn.sendall(data)
    taken = perf.perf_counter() - start
    conn.close()
    return taken

def bench_native_udp(loops):
    conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return _sendto(loops, conn, SMALL_DATA, len(BIG_DATA))
    finally:
        conn.close()

def bench_gevent_udp(loops):
    conn = gsocket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        return _sendto(loops, conn, SMALL_DATA, len(BIG_DATA))
    finally:
        conn.close()

def bench_native_thread_default_socketpair(loops):
    send, recv = socket.socketpair()
    t = threading.Thread(target=recvall, args=(recv, None))
    t.daemon = True
    t.start()

    return _sendall(loops, send, BIG_DATA)

def bench_gevent_greenlet_default_socketpair(loops):
    send, recv = gsocket.socketpair()
    gevent.spawn(recvall, recv, None)

    return _sendall(loops, send, BIG_DATA)


def main():
    runner = perf.Runner()

    runner.bench_time_func(
        'native socketpair sendall',
        bench_native_thread_default_socketpair,
        inner_loops=N)
    runner.bench_time_func(
        'gevent socketpair sendall',
        bench_gevent_greenlet_default_socketpair,
        inner_loops=N)

    runner.bench_time_func(
        'native udp sendto',
        bench_native_udp,
        inner_loops=N)
    runner.bench_time_func(
        'gevent udp sendto',
        bench_gevent_udp,
        inner_loops=N)


if __name__ == "__main__":
    main()
