import time
import gevent
from collections import OrderedDict
from enum import Enum
import itertools


class Strategy(Enum):
    ONE_FOR_ONE = 1
    ONE_FOR_ALL = 2
    REST_FOR_ONE = 3


class SupervisorCrash(Exception):
    pass


class Supervisor:
    def __init__(self, strategy=Strategy.ONE_FOR_ONE, max_restarts=5, time_frame=5, error_cb=None):
        self.counter = itertools.count()
        self.strategy = strategy
        if Strategy.REST_FOR_ONE == self.strategy:
            self.childs = OrderedDict()  # We must preserve the order
        else:
            self.childs = {}
        self.max_restarts = max_restarts
        self.time_frame = time_frame  # Seconds
        self.error_cb = error_cb

    def child_fails(self, _child):
        child = self.childs.get(_child._uid)
        if child:
            if self.error_cb is not None:
                self.error_cb(_child._exc_info)

            def append_time(c):
                res = c[3]
                if res is None:
                    res = []
                res.append(time.time())
                return res

            if self.strategy == Strategy.ONE_FOR_ONE:
                self.start_child(child[0], *child[1], _restarts=append_time(child), _uid=_child._uid, **child[2])
            elif self.strategy == Strategy.ONE_FOR_ALL:
                for uid, ch in self.childs.items():
                    ch[4].kill(block=True)
                    self.start_child(ch[0], *ch[1], _restarts=append_time(ch), _uid=uid, **ch[2])
            elif self.strategy == Strategy.REST_FOR_ONE:
                found = False
                _uid = _child._uid
                for uid, ch in self.childs.items():
                    if uid == _uid:
                        found = True
                    if found:
                        ch[4].kill(block=True)
                        self.start_child(ch[0], *ch[1], _restarts=append_time(ch), _uid=uid, **ch[2])
    

    def supress_errors(self):
        gevent.get_hub().NOT_ERROR = (Exception)

    def stop(self):
        gevent.get_hub().parent.throw(SupervisorCrash())
        print("Stopped")

    def start_child(self, func, *args, _restarts=None, _uid=None, **kwargs):
        if _restarts:
            ct = time.time()
            n_restarts = []
            for restart in _restarts:
                if ct - restart <= self.time_frame:
                    n_restarts.append(restart)
            if len(n_restarts) > self.max_restarts:
                self.stop()
                return
            _restarts = n_restarts

        child = gevent.spawn(func, *args, **kwargs)
        child.link_exception(self.child_fails)
        if _uid is None:
            _uid = self.counter.__next__()
        child._uid = _uid
        self.childs[_uid] = (child._run, child.args, child.kwargs, _restarts, child)
