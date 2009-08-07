from gevent import core
from gevent import coros
from gevent import rawgreenlet
from gevent.hub import getcurrent, GreenletExit
from gevent.greenlet import spawn, spawn_link, spawn_link_value, spawn_link_exception, joinall

class GreenletSet(object):
    """Maintain a set of greenlets that are still running.
    
    Links to each item and removes it upon notification.
    """

    def __init__(self, *args):
        self.procs = set(*args)
        self.dying = set()
        if args:
            for p in args[0]:
                p.link(self.discard)

    def __repr__(self):
        try:
            classname = self.__class__.__name__
        except AttributeError:
            classname = 'ProcSet'
        return '<%s at %s procs=%s dying=%s>' % (classname, hex(id(self)), self.procs, self.dying)

    def __len__(self):
        return len(self.procs) + len(self.dying)

    def __contains__(self, item):
#         if isinstance(item, greenlet):
#             # XXX should not be necessary
#             # special case for "getcurrent() in running_proc_set" to work
#             for x in self.procs:
#                 if x.greenlet == item:
#                     return True
#             for x in self.dying:
#                 if x.greenlet == item:
#                     return True
#             # hack Proc's __hash__ and __eq__ to avoid special casing this?
#             # in this case, instead of a hack. maybe make Proc a subclass of greenlet?
#         else:
        return item in self.procs or item in self.dying

    def __iter__(self):
        return iter(self.procs+self.dying)

    def add(self, p):
        self.procs.add(p)
        p.link(self.discard)
        # QQQ check if Proc can be fixed to support p.link(self.procs.discard)

    def discard(self, p):
        self.procs.discard(p)
        self.dying.discard(p)

    def spawn(self, func, *args, **kwargs):
        p = spawn(func, *args, **kwargs)
        self.add(p)
        return p

    def spawn_link(self, func, *args, **kwargs):
        p = spawn_link(func, *args, **kwargs)
        self.add(p)
        return p

    def spawn_link_value(self, func, *args, **kwargs):
        p = spawn_link_value(func, *args, **kwargs)
        self.add(p)
        return p

    def spawn_link_exception(self, func, *args, **kwargs):
        p = spawn_link_exception(func, *args, **kwargs)
        self.add(p)
        return p

    def joinall(self, raise_error=False):
        while self.procs:
            joinall(self.procs, raise_error=raise_error)

    def kill(self, p, exception=GreenletExit, block=False):
        kill = p.kill
        try:
            self.procs.remove(p)
        except KeyError:
            return
        self.dying.add(p)
        return kill(exception=exception, block=block)

    def killall(self, exception=GreenletExit, block=False):
        while self.procs or self.dying:
            for p in self.procs:
                core.active_event(p.throw, exception)
            self.dying.update(self.procs)
            self.procs.clear()
            if not block:
                break
            if self.dying:
                joinall(self.dying)


# make interface similar to standard library pools in multiprocessing

class Pool(object):

    def __init__(self, size=100):
        self.sem = coros.Semaphore(size)
        self.procs = GreenletSet()

    @property
    def current_size(self):
        return len(self.procs)

    def free_count(self):
        return self.sem.counter

    def execute(self, func, *args, **kwargs):
        """Execute func in one of the coroutines maintained
        by the pool, when one is free.

        Immediately returns a Proc object which can be queried
        for the func's result.

        >>> pool = Pool()
        >>> task = pool.execute(lambda a: ('foo', a), 1)
        >>> task.get()
        ('foo', 1)
        """
        # if reentering an empty pool, don't try to wait on a coroutine freeing
        # itself -- instead, just execute in the current coroutine
        if self.sem.locked() and getcurrent() in self.procs:
            p = spawn(func, *args, **kwargs)
            p.join()
        else:
            self.sem.acquire()
            p = self.procs.spawn(func, *args, **kwargs)
            # assuming the above line cannot raise
            p.link(lambda p: self.sem.release())
        return p

    def execute_async(self, func, *args, **kwargs):
        if self.sem.locked():
            return rawgreenlet.spawn(self.execute, func, *args, **kwargs)
        else:
            return self.execute(func, *args, **kwargs)

    def _execute(self, evt, func, args, kw):
        p = self.execute(func, *args, **kw)
        p.link(evt)
        return p

    def joinall(self): # XXX use just join?
        return self.procs.joinall()

    def killall(self):
        return self.procs.killall()

