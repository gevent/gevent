from __future__ import absolute_import, print_function, division

# Best run with dnsmasq configured as a caching nameserver
# with no timeouts and configured to point there via
# /etc/resolv.conf and GEVENT_RESOLVER_NAMESERVERS
# Remember to use --inherit-environ to make that work!

# dnsmasq -d --cache-size=100000 --local-ttl=1000000 --neg-ttl=10000000
#    --max-ttl=100000000 --min-cache-ttl=10000000000  --no-poll --auth-ttl=100000000000
from gevent import monkey; monkey.patch_all()
import sys
import socket

import perf
import gevent


from zope.dottedname.resolve import resolve as drresolve

blacklist = {
    22, 55, 68, 69, 72, 52, 94, 62, 54, 71, 73, 74, 34, 36,
    83, 86, 79, 81, 98, 99, 120, 130, 152, 161, 165, 169,
    172, 199, 205, 239, 235, 254, 256, 286, 299, 259, 229,
    190, 185, 182, 173, 160, 158, 153, 139, 138, 131, 129,
    127, 125, 116, 112, 110, 106,
}

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
            res.gethostbyname('x%s.com' % index)
        except socket.gaierror:
            pass

def resolve_par(res, count=10, begin=0):
    gs = []
    for index in range(begin, count + begin):
        if index in blacklist:
            continue
        gs.append(gevent.spawn(quiet, res.gethostbyname, 'x%s.com' % index))
    gevent.joinall(gs)

N = 300

def run_all(resolver_name, resolve):

    res = drresolve('gevent.resolver.' + resolver_name + '.Resolver')
    res = res()
    # dnspython looks up cname aliases by default, but c-ares does not.
    # dnsmasq can only cache one address with a given cname at a time,
    # and many of our addresses clash on that, so dnspython is put at a
    # severe disadvantage. We turn that off here.
    res._getaliases = lambda hostname, family: []

    if N > 150:
        # 150 is the max concurrency in dnsmasq
        count = N // 3
        resolve(res, count=count)
        resolve(res, count=count, begin=count)
        resolve(res, count=count, begin=count * 2)
    else:
        resolve(res, count=N)


def main():
    def worker_cmd(cmd, args):
        cmd.extend(args.benchmark)

    runner = perf.Runner(processes=5, values=3,
                         add_cmdline_args=worker_cmd)

    all_names = 'dnspython', 'blocking', 'ares', 'thread'
    runner.argparser.add_argument('benchmark',
                                  nargs='*',
                                  default='all',
                                  choices=all_names + ('all',))


    args = runner.parse_args()

    if 'all' in args.benchmark or args.benchmark == 'all':
        args.benchmark = ['all']
        names = all_names
    else:
        names = args.benchmark

    for name in names:
        runner.bench_func(name + ' sequential',
                          run_all,
                          name, resolve_seq,
                          inner_loops=N)
        runner.bench_func(name + ' parallel',
                          run_all,
                          name, resolve_par,
                          inner_loops=N)

if __name__ == '__main__':
    main()
