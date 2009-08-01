# Copyright (c) 2008-2009 AG Projects
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

"""Advanced coroutine control.

This module provides means to spawn, kill and link coroutines. Linking means
subscribing to the coroutine's result, either in form of return value or
unhandled exception.

To create a linkable coroutine use spawn function provided by this module:

>>> def demofunc(x, y):
...    return x / y

>>> p = spawn(demofunc, 6, 2)

The return value of spawn is an instance of Proc class that you can "link":

 * p.link(obj) - notify obj when the coroutine is finished

What does "notify" means here depends on the type of `obj': a callable is
simply called, an event or a queue is notified using send/send_exception
methods and if `obj' is another greenlet it's killed with LinkedExited
exception.

Here's an example:
>>> event = coros.event()
>>> _ = p.link(event)
>>> event.wait()
3

Now, even though `p' is finished it's still possible to link it. In this
case the notification is performed immediatelly:

>>> try:
...     p.link()
... except LinkedCompleted:
...     print 'LinkedCompleted'
LinkedCompleted

(Without an argument, link is created to the current greenlet)

There are also link_value and link_exception methods that only deliver a return
value and an unhandled exception respectively (plain `link' deliver both).
Suppose we want to spawn a greenlet to do an important part of the task; if it
fails then there's no way to complete the task so the parent must fail as well;
`link_exception' is useful here:

>>> p = spawn(demofunc, 1, 0)
>>> _ = p.link_exception()
>>> try:
...     greenlet.sleep(1)
... except LinkedFailed:
...     print 'LinkedFailed'
LinkedFailed

One application of linking is `waitall' function: link to a bunch of coroutines
and wait for all them to complete. Such function is provided by this module.
"""
import sys
from gevent import coros, greenlet, core
from gevent.queue import Queue
import traceback

__all__ = ['LinkedExited',
           'LinkedFailed',
           'LinkedCompleted',
           'LinkedKilled',
           'waitall',
           'killall'
           'Source',
           'Proc',
           'spawn',
           'spawn_link',
           'spawn_link_value',
           'spawn_link_exception']


class LinkedExited(Exception):
    """Raised when a linked proc exits"""
    msg = "%r exited"

    def __init__(self, name=None, msg=None):
        self.name = name
        if msg is None:
            msg = self.msg % self.name
        Exception.__init__(self, msg)

class LinkedCompleted(LinkedExited):
    """Raised when a linked proc finishes the execution cleanly"""

    msg = "%r completed successfully"

class LinkedFailed(LinkedExited):
    """Raised when a linked proc dies because of unhandled exception"""
    msg = "%r failed with %s"

    def __init__(self, name, typ, value=None, tb=None):
        msg = self.msg % (name, typ.__name__)
        LinkedExited.__init__(self, name, msg)

class LinkedKilled(LinkedFailed):
    """Raised when a linked proc dies because of unhandled GreenletExit
    (i.e. it was killed)
    """
    msg = """%r was killed with %s"""

def getLinkedFailed(name, typ, value=None, tb=None):
    if issubclass(typ, greenlet.GreenletExit):
        return LinkedKilled(name, typ, value, tb)
    return LinkedFailed(name, typ, value, tb)


class ProcExit(greenlet.GreenletExit):
    """Raised when this proc is killed."""


class Link(object):

    def __init__(self, listener):
        self.listener = listener

    def cancel(self):
        self.listener = None

    def __enter__(self):
        pass

    def __exit__(self, *args):
        self.cancel()

class LinkToEvent(Link):

    def __call__(self, source):
        if self.listener is not None:
            if source.has_value():
                self.listener.send(source.value)
            else:
                self.listener.send_exception(*source.exc_info())

class LinkToGreenlet(Link):

    def __call__(self, source):
        if self.listener is not None:
            if source.has_value():
                self.listener.throw(LinkedCompleted(source.name))
            else:
                self.listener.throw(getLinkedFailed(source.name, *source.exc_info()))

class LinkToCallable(Link):

    def __call__(self, source):
        if self.listener is not None:
            self.listener(source)


# QQQ add timeout
def joinall(sources, trap_errors=True, queue=None):
    if queue is None:
        queue = Queue()
    links = []
    try:
        for source in sources:
            links.append(source.link(queue.put))
        for _ in xrange(len(sources)):
            completed = queue.get()
            if not trap_errors and completed.has_exception():
                greenlet.getcurrent().throw(*completed.exc_info())
    finally:
        for link in links:
            link.cancel()


def waitall(sources, trap_errors=False, queue=None):
    joinall(sources, trap_errors=trap_errors, queue=queue)
    return [source.value for source in sources]


def killall(sources, exception=ProcExit, block=False, polling_period=0.2):
    waiter = greenlet.Waiter()
    core.active_event(greenlet._killall, sources, exception, waiter)
    if block:
        alive = waiter.wait()
        if alive:
            try:
                joinall(alive, trap_errors=True)
            except TypeError:
                greenlet._joinall(alive, polling_period=polling_period)
            # QQQ a) use links for all the greenlets we can and poll the others
            # QQQ b) have only one unversal version of killall, waitall, joinall etc
            # QQQ    the current dichotomy of greenlets and procs is confusing


class NotUsed(object):

    def __str__(self):
        return '<Source instance does not hold a value or an exception>'

    __repr__ = __str__

_NOT_USED = NotUsed()


def limitrepr(obj, limit=50):
    res = repr(obj)
    if len(res)>limit:
        res = res[:limit]+'...'
    return res


def spawn_greenlet(function, *args):
    """Create a new greenlet that will run `function(*args)'.
    The current greenlet won't be unscheduled. Keyword arguments aren't
    supported (limitation of greenlet), use spawn() to work around that.
    """
    import warnings
    warnings.warn("gevent.proc.spawn_greenlet is deprecated; use gevent.spawn", DeprecationWarning, stacklevel=2)
    g = greenlet.Greenlet(function)
    g.parent = greenlet.get_hub().greenlet
    core.active_event(g.switch, *args)
    return g


class Source(object):
    """Maintain a set of links to the listeners. Delegate the sent value or
    the exception to all of them.

    To set up a link, use link_value, link_exception or link method. The
    latter establishes both "value" and "exception" link. It is possible to
    link to events, queues, greenlets and callables.

    >>> source = Source()
    >>> event = coros.event()
    >>> _ = source.link(event)

    Once source's send or send_exception method is called, all the listeners
    with the right type of link will be notified ("right type" means that
    exceptions won't be delivered to "value" links and values won't be
    delivered to "exception" links). Once link has been fired it is removed.

    Notifying listeners is performed in the MAINLOOP greenlet. Under the hood
    notifying a link means executing a callback, see Link class for details. Notification
    must not attempt to switch to the hub, i.e. call any of blocking functions.

    >>> source.send('hello')
    >>> event.wait()
    'hello'

    Any error happened while sending will be logged as a regular unhandled
    exception. This won't prevent other links from being fired.

    There 3 kinds of listeners supported:

     1. If `listener' is a greenlet (regardless if it's a raw greenlet or an
        extension like Proc), a subclass of LinkedExited exception is raised
        in it.

     2. If `listener' is something with send/send_exception methods (event,
        queue, Source but not Proc) the relevant method is called.

     3. If `listener' is a callable, it is called with 1 argument (the result)
        for "value" links and with 3 arguments (typ, value, tb) for "exception"
        links.
    """

    def __init__(self, name=None):
        self.name = name
        self._value_links = {}
        self._exception_links = {}
        self.value = _NOT_USED
        self._exc = None

    def _repr_helper(self):
        result = []
        result.append(repr(self.name))
        if self.value is not _NOT_USED:
            if self._exc is None:
                result.append('result=%s' % limitrepr(self.value))
            else:
                result.append('raised=%s' % limitrepr(self.exc_info()[1]))
        result.append('{%s:%s}' % (len(self._value_links), len(self._exception_links)))
        return result

    def __repr__(self):
        klass = type(self).__name__
        return '<%s at %s %s>' % (klass, hex(id(self)), ' '.join(self._repr_helper()))

    def ready(self):
        return self.value is not _NOT_USED

    def has_value(self):
        return self.value is not _NOT_USED and self._exc is None

    def has_exception(self):
        return self.value is not _NOT_USED and self._exc is not None

    def exc_info(self):
        if not self._exc:
            return (None, None, None)
        elif len(self._exc)==3:
            return self._exc
        elif len(self._exc)==1:
            if isinstance(self._exc[0], type):
                return self._exc[0], None, None
            else:
                return self._exc[0].__class__, self._exc[0], None
        elif len(self._exc)==2:
            return self._exc[0], self._exc[1], None
        else:
            return self._exc

    def link_value(self, listener=None, link=None):
        if self.ready() and self._exc is not None:
            return
        if listener is None:
            listener = greenlet.getcurrent()
        if link is None:
            link = self.getLink(listener)
        if self.ready() and listener is greenlet.getcurrent():
            link(self)
        else:
            self._value_links[listener] = link
            if self.value is not _NOT_USED:
                self._start_send()
        return link

    def link_exception(self, listener=None, link=None):
        if self.value is not _NOT_USED and self._exc is None:
            return
        if listener is None:
            listener = greenlet.getcurrent()
        if link is None:
            link = self.getLink(listener)
        if self.ready() and listener is greenlet.getcurrent():
            link(self)
        else:
            self._exception_links[listener] = link
            if self.value is not _NOT_USED:
                self._start_send_exception()
        return link

    def link(self, listener=None, link=None):
        if listener is None:
            listener = greenlet.getcurrent()
        if link is None:
            link = self.getLink(listener)
        if self.ready() and listener is greenlet.getcurrent():
            if self._exc is None:
                link(self)
            else:
                link(self)
        else:
            self._value_links[listener] = link
            self._exception_links[listener] = link
            if self.value is not _NOT_USED:
                if self._exc is None:
                    self._start_send()
                else:
                    self._start_send_exception()
        return link

    def unlink(self, listener=None):
        if listener is None:
            listener = greenlet.getcurrent()
        self._value_links.pop(listener, None)
        self._exception_links.pop(listener, None)

    @staticmethod
    def getLink(listener):
        if hasattr(listener, 'throw'):
            return LinkToGreenlet(listener)
        if hasattr(listener, 'send'):
            return LinkToEvent(listener)
        elif callable(listener):
            return LinkToCallable(listener)
        else:
            raise TypeError("Don't know how to link to %r" % (listener, ))

    def send(self, value=None):
        assert not self.ready(), "%s has been fired already" % self
        self.value = value
        self._exc = None
        self._start_send()

    def _start_send(self):
        core.active_event(self._do_send, self._value_links.items(), self._value_links)

    def send_exception(self, *throw_args):
        assert not self.ready(), "%s has been fired already" % self
        self.value = None
        self._exc = throw_args
        self._start_send_exception()

    def _start_send_exception(self):
        core.active_event(self._do_send, self._exception_links.items(), self._exception_links)

    def _do_send(self, links, consult):
        while links:
            listener, link = links.pop()
            try:
                if listener in consult:
                    try:
                        link(self)
                    finally:
                        consult.pop(listener, None)
            except:
                traceback.print_exc()
                try:
                    sys.stderr.write('Failed to execute link %s to %s\n\n' % (listener, self))
                except:
                    pass

    def wait(self, timeout=None, exception=None):
        """Wait until send() or send_exception() is called or `timeout' has
        expired. Return the argument of send or raise the argument of
        send_exception. If timeout has expired, None is returned.

        The arguments, when provided, specify how many seconds to wait and what
        to do when timeout has expired. They are treated the same way as
        timeout treats them.
        """
        if self.value is not _NOT_USED:
            if self._exc is None:
                return self.value
            else:
                greenlet.getcurrent().throw(*self._exc)
        elif timeout is None:
            waiter = Waiter()
            self.link(waiter)
            try:
                return waiter.wait()
            finally:
                self.unlink(waiter)
        elif timeout <= 0:
            if exception is False:
                return
            if exception is None:
                exception = greenlet.Timeout()
            raise exception
        else:
            # what follows is:
            # with greenlet.Timeout(timeout, *throw_args):
            #     waiter = Waiter()
            #     self.link(waiter)
            #     try:
            #         return waiter.wait()
            #     finally:
            #         self.unlink(waiter)
            # however, with statement is hand decompiled to make it 2.4 compatible
            timer = greenlet.Timeout(timeout, exception)
            EXC = True
            try:
                try:
                    waiter = Waiter()
                    self.link(waiter)
                    try:
                        return waiter.wait()
                    finally:
                        self.unlink(waiter)
                except:
                    EXC = False
                    if not timer.__exit__(*sys.exc_info()):
                        raise
            finally:
                if EXC:
                    timer.__exit__(None, None, None)
    # QQQ allow exception to be a tuple?


class Waiter(object):
    # XXX: reuse Waiter from gevent and remove this one

    def __init__(self):
        self.greenlet = None

    def send(self, value=None):
        """Wake up the greenlet that is calling wait() currently (if there is one).
        Can only be called from get_hub().greenlet.
        """
        assert greenlet.getcurrent() is greenlet.get_hub().greenlet
        if self.greenlet is not None:
            self.greenlet.switch(value)

    def send_exception(self, *throw_args):
        """Make greenlet calling wait() wake up (if there is a wait()).
        Can only be called from greenlet.get_hub().greenlet.
        """
        assert greenlet.getcurrent() is greenlet.get_hub().greenlet
        if self.greenlet is not None:
            self.greenlet.throw(*throw_args)

    def wait(self):
        """Wait until send or send_exception is called. Return value passed
        into send() or raise exception passed into send_exception().
        """
        assert self.greenlet is None
        current = greenlet.getcurrent()
        assert current is not greenlet.get_hub().greenlet
        self.greenlet = current
        try:
            return greenlet.get_hub().switch()
        finally:
            self.greenlet = None


class Proc(Source):
    """A linkable coroutine based on Source.
    Upon completion, delivers coroutine's result to the listeners.
    """

    def __init__(self, name=None):
        self.greenlet = None
        Source.__init__(self, name)

    def _repr_helper(self):
        if self.greenlet is not None and self.greenlet.dead:
            dead = '(dead)'
        else:
            dead = ''
        return ['%r%s' % (self.greenlet, dead)] + Source._repr_helper(self)

    def __repr__(self):
        klass = type(self).__name__
        return '<%s %s>' % (klass, ' '.join(self._repr_helper()))

    def __nonzero__(self):
        if self.ready():
            # with current _run this does not makes any difference
            # still, let keep it there
            return False
        # otherwise bool(proc) is the same as bool(greenlet)
        if self.greenlet is not None:
            return bool(self.greenlet)

    @property
    def dead(self):
        return self.ready() or self.greenlet.dead

    @classmethod
    def spawn(cls, function, *args, **kwargs):
        """Return a new Proc instance that is scheduled to execute
        function(*args, **kwargs) upon the next hub iteration.
        """
        proc = cls()
        proc.run(function, *args, **kwargs)
        return proc

    def run(self, function, *args, **kwargs):
        """Create a new greenlet to execute `function(*args, **kwargs)'.
        The created greenlet is scheduled to run upon the next hub iteration.
        """
        assert self.greenlet is None, "'run' can only be called once per instance"
        if self.name is None:
            self.name = str(function)
        self.greenlet = greenlet.spawn(self._run, function, args, kwargs)

    def _run(self, function, args, kwargs):
        """Internal top level function.
        Execute *function* and send its result to the listeners.
        """
        try:
            result = function(*args, **kwargs)
        except:
            self.send_exception(*sys.exc_info())
            raise # let mainloop log the exception
        else:
            self.send(result)

    def throw(self, *throw_args):
        """Used internally to raise the exception.

        Behaves exactly like greenlet's 'throw' with the exception that ProcExit
        is raised by default. Do not use this function as it leaves the current
        greenlet unscheduled forever. Use kill() method instead.
        """
        if not self.dead:
            if not throw_args:
                throw_args = (ProcExit, )
            self.greenlet.throw(*throw_args)

    def kill(self, exception=ProcExit, block=False):
        if not self.dead:
            core.active_event(self.greenlet.throw, exception)
            if block:
                try:
                    self.wait()
                except:
                    pass

    # QQQ maybe Proc should not inherit from Source (because its send() and send_exception()
    # QQQ methods are for internal use only)


spawn = Proc.spawn

def spawn_link(function, *args, **kwargs):
    p = spawn(function, *args, **kwargs)
    p.link()
    return p

def spawn_link_value(function, *args, **kwargs):
    p = spawn(function, *args, **kwargs)
    p.link_value()
    return p

def spawn_link_exception(function, *args, **kwargs):
    p = spawn(function, *args, **kwargs)
    p.link_exception()
    return p


def spawn_later(seconds, function, *args, **kwargs):
    # XXX implement properly, without scheduling 2 events instead of 1
    core.timer(seconds, spawn, function, *args, **kwargs)


# QQQ not specific to proc module: move to greenlet.py?
class wrap_errors(object):
    """Helper to make function return an exception, rather than raise it.

    Because every exception that is unhandled by greenlet will be logged by the hub,
    it is desirable to prevent non-error exceptions from leaving a greenlet.
    This can done with simple try/except construct:

    def func1(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (A, B, C), ex:
            return ex

    wrap_errors provides a shortcut to write that in one line:

    func1 = wrap_errors((A, B, C), func)

    It also preserves __str__ and __repr__ of the original function.
    """

    def __init__(self, errors, func):
        """Make a new function from `func', such that it catches `errors' (an
        Exception subclass, or a tuple of Exception subclasses) and return
        it as a value.
        """
        self.errors = errors
        self.func = func

    def __call__(self, *args, **kwargs):
        try:
            return self.func(*args, **kwargs)
        except self.errors, ex:
            return ex

    def __str__(self):
        return str(self.func)

    def __repr__(self):
        return repr(self.func)

    def __getattr__(self, item):
        return getattr(self.func, item)


class ProcSet(object):
    """Maintain a set of Procs that are still running, that is, automatically remove
    a proc when it's finished. Provide a way to wait/kill all of them"""

    def __init__(self, *args):
        self.procs = set(*args)
        if args:
            for p in args[0]:
                p.link(self.discard)
        self.dying = set()

    def __repr__(self):
        try:
            classname = self.__class__.__name__
        except AttributeError:
            classname = 'ProcSet'
        return '<%s at %s procs=%s dying=%s>' % (classname, hex(id(self)), self.procs, self.dying)

    def __len__(self):
        return len(self.procs) + len(self.dying)

    def __contains__(self, item):
        if isinstance(item, greenlet.Greenlet):
            # special case for "getcurrent() in running_proc_set" to work
            for x in self.procs:
                if x.greenlet == item:
                    return True
            for x in self.dying:
                if x.greenlet == item:
                    return True
            # hack Proc's __hash__ and __eq__ to avoid special casing this?
        else:
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

    def waitall(self, trap_errors=True):
        while self.procs:
            waitall(self.procs, trap_errors=trap_errors)

    def kill(self, p, exception=ProcExit, block=False):
        kill = p.kill
        try:
            self.procs.remove(p)
        except KeyError:
            return
        self.dying.add(p)
        return kill(exception=exception, block=block)

    def killall(self, exception=ProcExit, block=False):
        while self.procs or self.dying:
            for p in self.procs:
                core.active_event(p.throw, exception)
            self.dying.update(self.procs)
            self.procs.clear()
            if not block:
                break
            if self.dying:
                waitall(self.dying, trap_errors=True)


RunningProcSet = ProcSet # XXX deprecated name, will be removed


class Pool(object):

    def __init__(self, size=100):
        self.sem = coros.Semaphore(size)
        self.procs = RunningProcSet()

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
        >>> task.wait()
        ('foo', 1)
        """
        # if reentering an empty pool, don't try to wait on a coroutine freeing
        # itself -- instead, just execute in the current coroutine
        if self.sem.locked() and greenlet.getcurrent() in self.procs:
            p = spawn(func, *args, **kwargs)
            try:
                p.wait()
            except:
                pass
        else:
            self.sem.acquire()
            p = self.procs.spawn(func, *args, **kwargs)
            # assuming the above line cannot raise
            p.link(lambda p: self.sem.release())
        return p

    def execute_async(self, func, *args, **kwargs):
        if self.sem.locked():
            return greenlet.spawn(self.execute, func, *args, **kwargs)
        else:
            return self.execute(func, *args, **kwargs)

    def _execute(self, evt, func, args, kw):
        p = self.execute(func, *args, **kw)
        p.link(evt)
        return p

    def waitall(self):
        return self.procs.waitall()

    def killall(self):
        return self.procs.killall()

