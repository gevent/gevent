from __future__ import absolute_import, print_function

# Best run with dnsmasq configured as a caching nameserver
# with no timeouts and configured to point there via
# /etc/resolv.conf and GEVENTARES_SERVERS=

import gevent.monkey; gevent.monkey.patch_all()
import gevent
import sys
import socket
import time
from zope.dottedname.resolve import resolve as drresolve

blacklist = {22, 55, 68, 69, 99, 120, 130, 152, 161, 165, 169, 172,
             199, 205, 239, 235, 254, 256}

RUN_COUNT = 15 if hasattr(sys, 'pypy_version_info') else 5

def quiet(f, n):
    try:
        f(n)
    except socket.gaierror:
        pass

def resolve_seq(res, count=10, begin=0):
    for index in range(begin, count + begin):
        if index in blacklist:
            continue
        try:
            res.gethostbyname('www.x%s.com' % index)
        except socket.gaierror:
            pass

def resolve_par(res, count=10, begin=0):
    gs = []
    for index in range(begin, count + begin):
        if index in blacklist:
            continue
        gs.append(gevent.spawn(quiet, res.gethostbyname, 'www.x%s.com' % index) )
    gevent.joinall(gs)


def run_all(name, resolve=resolve_par):
    count = 100

    res = drresolve('gevent.resolver.' + name + '.Resolver')

    before = time.time()
    resolve(res(), count=count)
    after1 = time.time()
    resolve(res(), count=count, begin=count)
    after2 = time.time()
    resolve(res(), count=count, begin=count * 2)
    after3 = time.time()

    return (name, before, after1, after2, after3)

def make_results():
    result_map = {}

    names = 'dnspython', 'blocking', 'ares', 'thread'

    for name in names:
        print("Testing", name)
        results = []
        for _ in range(RUN_COUNT):
            r = run_all(name)
            delta = r[-1] - r[1]
            print("\t%.2f" % delta, end="")
            sys.stdout.flush()
            results.append((delta, r))
        results.sort()
        best = results[0]
        print("\n%s: best of %d runs: %.2f; worst: %.2f" % (name, RUN_COUNT, best[0], results[-1][0]))
        result_map[name] = best[1]

    return [result_map[x] for x in names]

results = make_results()

print('| Resolver  | One Iteration | Three Iterations | Delta 3 - two | ')
print('| --------  | ------------: | ----------------:| -------------:|' )

for result in results:
    name, before, after1, after2, after3 = result

    one_it = after1 - before
    two_it = after2 - before
    three_it = after3 - before
    delta2 = after2 - after1
    delta = after3 - after2

    print("| %9s | %13.2f | %16.2f | %13.2f |" % (name, one_it, three_it, delta))
