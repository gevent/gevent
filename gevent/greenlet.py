# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

import sys
import traceback
from gevent import core
from gevent.hub import greenlet, getcurrent, get_hub, GreenletExit, Waiter, kill
from gevent.timeout import Timeout
from gevent.util import lazy_property


__all__ = ['Greenlet',
           'joinall',
           'killall']


class SpawnedLink(object):
    """A wrapper around link that calls it in another greenlet.

    Can be called only from main loop.
    """
    __slots__ = ['callback']

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, source):
        g = greenlet(self.callback, get_hub())
        g.switch(source)

    def __hash__(self):
        return hash(self.callback)

    def __eq__(self, other):
        return self.callback == getattr(other, 'callback', other)

    def __str__(self):
        return str(self.callback)

    def __repr__(self):
        return repr(self.callback)

    def __getattr__(self, item):
        assert item != 'callback'
        return getattr(self.callback, item)


class SuccessSpawnedLink(SpawnedLink):
    """A wrapper around link that calls it in another greenlet only if source succeed.

    Can be called only from main loop.
    """
    __slots__ = []

    def __call__(self, source):
        if source.successful():
            return SpawnedLink.__call__(self, source)


class FailureSpawnedLink(SpawnedLink):
    """A wrapper around link that calls it in another greenlet only if source failed.

    Can be called only from main loop.
    """
    __slots__ = []

    def __call__(self, source):
        if not source.successful():
            return SpawnedLink.__call__(self, source)


class GreenletLink(object):
    """A wrapper around greenlet that raises a LinkedExited exception when called.

    Can be called only from main loop.
    """
    __slots__ = ['greenlet']

    def __init__(self, greenlet):
        self.greenlet = greenlet

    def __call__(self, source):
        if source.successful():
            error = getLinkedCompleted(source)
        else:
            error = LinkedFailed(source)
        current = getcurrent()
        greenlet = self.greenlet
        if current is greenlet:
            greenlet.throw(error)
        elif current is get_hub():
            try:
                greenlet.throw(error)
            except:
                traceback.print_exc()
        else:
            kill(self.greenlet, error)

    def __hash__(self):
        return hash(self.greenlet)

    def __eq__(self, other):
        return self.greenlet == getattr(other, 'greenlet', other)

    def __str__(self):
        return str(self.greenlet)

    def __repr__(self):
        return repr(self.greenlet)


class SuccessGreenletLink(GreenletLink):
    """A wrapper around greenlet that raises a LinkedExited exception when called
    if source has succeed.

    Can be called only from main loop.
    """
    __slots__ = []

    def __call__(self, source):
        if source.successful():
            return GreenletLink.__call__(self, source)


class FailureGreenletLink(GreenletLink):
    """A wrapper around greenlet that raises a LinkedExited exception when called
    if source has failed.

    Can be called only from main loop.
    """
    __slots__ = []

    def __call__(self, source):
        if not source.successful():
            return GreenletLink.__call__(self, source)


class Greenlet(greenlet):
    """A greenlet subclass that adds a few features:
        - join  - wait for the greenlet to exit
        - kill  - raise the exception in the greenlet
        - get   - return the result of the greenlet
        - link  - register a callable to notify upon greenlet exit
        - ready
        - successful

    Additionally,
        -'value' attribute holds the result of the greenlet or None if the greenlet has no result.
        -'exception' attribute holds the exception instance that greenlet has raised or None

    To start a function in another greenlet, pass it and its arguments to Greenlet constructor
    and call start():
      
        >>> g = Greenlet(myfunction, 'arg1', 'arg2', kwarg1=1)
        >>> g.start()

    or use 'spawn' shortcut which does these 2 steps in one go:

        >>> g = Greenlet.spawn(myfunction, 'arg1', 'arg2', kwarg1=1)

    To subclass a Greenlet, override its _run method and don't forget
    to call Greenlet.__init__(self) in your subclass' __init__:

        >>> class MySleepGreenlet(Greenlet):
        ...
        ...     def __init__(self, seconds):
        ...         Greenlet.__init__(self)
        ...         self.seconds = seconds
        ...
        ...     def _run(self):
        ...         gevent.sleep(self.seconds)

    It also a good idea to override __str__: if the greenlet raises an exception,
    its string representation will be printed after the traceback it generated.
    """

    args = ()
    kwargs = {}
    
    def __init__(self, run=None, *args, **kwargs):
        greenlet.__init__(self, parent=get_hub())
        if run is not None:
            self._run = run
        if args:
            self.args = args
        if kwargs:
            self.kwargs = kwargs
        self._links = set()
        self.value = None
        self._exception = _NONE
        self._notifier = None
        self._start_event = None

    def ready(self):
        return self.dead or self._exception is not _NONE

    def successful(self):
        return self._exception is None

    def __repr__(self):
        classname = self.__class__.__name__
        result = '<%s at %s' % (classname, hex(id(self)))
        formatted = self._formatted_info
        if formatted is not None:
            result += ': ' + formatted
        return result + '>'

    @lazy_property
    def _formatted_info(self):
        try:
            result = getfuncname(self.__dict__['_run'])
        except Exception:
            pass
        else:
            args = []
            if self.args:
                args = [repr(x) for x in self.args]
            if self.kwargs:
                args.extend(['%s=%r' % x for x in self.kwargs.items()])
            if args:
                result += '(' + ', '.join(args) + ')'
            return result

    @property
    def exception(self):
        """If greenlet has failed, 'exception' property holds the exception instance."""
        if self._exception is not _NONE:
            return self._exception

    def throw(self, *args):
        if self._start_event is not None:
            self._start_event.cancel()
            self._start_event = None
        if not self.dead:
            if self:
                return greenlet.throw(self, *args)
            else:
                # special case for when greenlet is not yet started, because _report_error is not executed
                if len(args)==1:
                    self._exception = args[0]
                elif not args:
                    self._exception = GreenletExit()
                else:
                    self._exception = args[1]
                try:
                    return greenlet.throw(self, *args)
                finally:
                    if self._links and self._notifier is None:
                        self._notifier = core.active_event(self._notify_links)

    def start(self):
        """Must be called _exactly_ once for a greenlet to become active"""
        assert self._start_event is None, 'Greenlet already started'
        self._start_event = core.active_event(self.switch)

    def start_later(self, seconds):
        """Must be called _exactly_ once for a greenlet to become active"""
        assert self._start_event is None, 'Greenlet already started'
        self._start_event = core.timer(seconds, self.switch)

    @classmethod
    def spawn(cls, *args, **kwargs):
         g = cls(*args, **kwargs)
         g.start()
         return g

    @classmethod
    def spawn_later(cls, seconds, *args, **kwargs):
         g = cls(*args, **kwargs)
         g.start_later(seconds)
         return g

    @classmethod
    def spawn_link(cls, function, *args, **kwargs):
        g = cls.spawn(function, *args, **kwargs)
        g.link()
        return g

    @classmethod
    def spawn_link_value(cls, function, *args, **kwargs):
        g = cls.spawn(function, *args, **kwargs)
        g.link_value()
        return g

    @classmethod
    def spawn_link_exception(cls, function, *args, **kwargs):
        g = cls.spawn(function, *args, **kwargs)
        g.link_exception()
        return g

    def kill(self, exception=GreenletExit, block=False, timeout=None):
        """Raise the exception in the greenlet.

        By default (block is False), the current greenlet is not unscheduled:
        If block is True, wait for the greenlet to die or for the optional
        timeout to expire. If the timeout expires before the greenlet has died,
        stop waiting quietly.
        """
        if not self.dead:
            waiter = Waiter()
            core.active_event(_kill, self, exception, waiter)
            if block:
                waiter.wait()
                self.join(timeout)

    def get(self, block=True, timeout=None):
        """Return the result the greenlet has returned or re-raise the exception it has raised.

        If block is False, raise Timeout if the greenlet is still alive.
        If block is True, unschedule the current greenlet until the result is available
        or the timeout expires. In the latter case, Timeout is raised.
        """
        if self.ready():
            if self.successful():
                return self.value
            else:
                raise self._exception
        if block:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                t = Timeout.start_new(timeout)
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into Greenlet.get(): %r' % (result, )
                finally:
                    t.cancel()
            except:
                # unlinking in 'except' instead of finally is an optimization:
                # if switch occurred normally then link was already removed in _notify_links
                # and there's no need to touch the links set.
                # Note, however, that if "Invalid switch" assert was removed and invalid switch
                # did happen, the link would remain, causing another invalid switch later in this greenlet.
                self.unlink(switch)
                raise
            if self.ready():
                if self.successful():
                    return self.value
                else:
                    raise self._exception
        else:
            raise Timeout

    def join(self, timeout=None):
        """Wait for the greenlet to complete or for timeout to expire.

        Returns None, never raises anything.
        """
        if self.ready():
            return
        else:
            switch = getcurrent().switch
            self.rawlink(switch)
            try:
                t = Timeout.start_new(timeout)
                try:
                    result = get_hub().switch()
                    assert result is self, 'Invalid switch into Greenlet.join(): %r' % (result, )
                finally:
                    t.cancel()
            except:
                self.unlink(switch)
                raise

    def _report_result(self, result):
        self._exception = None
        self.value = result
        if self._links and self._notifier is None:
            self._notifier = core.active_event(self._notify_links)

    def _report_error(self, exc_info):
        try:
            if exc_info[0] is not None:
                traceback.print_exception(*exc_info)
        finally:
            self._exception = exc_info[1]
            if self._links and self._notifier is None:
                self._notifier = core.active_event(self._notify_links)
        
        info = str(self) + ' failed with '

        try:
            info += self._exception.__class__.__name__
        except Exception:
            info += str(self._exception) or repr(self._exception)
        sys.stderr.write(info + '\n\n')

    def run(self):
        try:
            self._start_event = None
            try:
                result = self._run(*self.args, **self.kwargs)
            except GreenletExit, ex:
                result = ex
            except:
                self._report_error(sys.exc_info())
                return
            self._report_result(result)
        finally:
            self.__dict__.pop('_run', None)
            self.__dict__.pop('args', None)
            self.__dict__.pop('kwargs', None)

    def rawlink(self, callback):
        """Register a callable to be executed when the greenlet finishes the execution.

        WARNING: the callable will be called in the HUB greenlet.
        """
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.add(callback)
        if self.ready() and self._notifier is None:
            self._notifier = core.active_event(self._notify_links)

    def link(self, receiver=None, GreenletLink=GreenletLink, SpawnedLink=SpawnedLink):
        """Link greenlet's completion to callable or another greenlet.

        receiver is None means link to the current greenlet.
        Always asynchronous, unless receiver is a current greenlet and the result is ready.
        """
        current = getcurrent()
        if receiver is None or receiver is current:
            receiver = GreenletLink(current)
            if self.ready():
                # special case : linking to current greenlet when link is ready
                # raise LinkedExited immediatelly
                receiver(self)
                return
        elif not callable(receiver):
            if isinstance(receiver, greenlet):
                receiver = GreenletLink(receiver)
            else:
                raise TypeError('Expected callable or greenlet: %r' % (receiver, ))
        else:
            receiver = SpawnedLink(receiver)
        self.rawlink(receiver)

    def unlink(self, receiver=None):
        if receiver is None:
            receiver = getcurrent()
        self._links.discard(receiver)

    def link_value(self, receiver=None, GreenletLink=SuccessGreenletLink, SpawnedLink=SuccessSpawnedLink):
        self.link(receiver=receiver, GreenletLink=GreenletLink, SpawnedLink=SpawnedLink)

    def link_exception(self, receiver=None, GreenletLink=FailureGreenletLink, SpawnedLink=FailureSpawnedLink):
        self.link(receiver=receiver, GreenletLink=GreenletLink, SpawnedLink=SpawnedLink)

    def _notify_links(self):
        try:
            while self._links:
                link = self._links.pop()
                try:
                    link(self)
                except:
                    traceback.print_exc()
                    try:
                        sys.stderr.write('Failed to notify link %s of %r\n\n' % (getfuncname(link), self))
                    except:
                        pass
        finally:
            self._notifier = None


def _kill(greenlet, exception, waiter):
    greenlet.throw(exception)
    waiter.switch()


def joinall(greenlets, timeout=None, raise_error=False):
    from gevent.queue import Queue
    queue = Queue()
    put = queue.put
    timeout = Timeout.start_new(timeout)
    try:
        try:
            for greenlet in greenlets:
                greenlet.rawlink(put)
            for _ in xrange(len(greenlets)):
                greenlet = queue.get()
                if raise_error and not greenlet.successful():
                    getcurrent().throw(greenlet.exception)
        except:
            for greenlet in greenlets:
                greenlet.unlink(put)
            raise
    finally:
        timeout.cancel()


def _killall3(greenlets, exception, waiter):
    diehards = []
    for g in greenlets:
        if not g.dead:
            try:
                g.throw(exception)
            except:
                traceback.print_exc()
            if not g.dead:
                diehards.append(g)
    waiter.switch(diehards)


def _killall(greenlets, exception):
    for g in greenlets:
        if not g.dead:
            try:
                g.throw(exception)
            except:
                traceback.print_exc()


def killall(greenlets, exception=GreenletExit, block=False, timeout=None):
    if block:
        waiter = Waiter()
        core.active_event(_killall3, greenlets, exception, waiter)
        if block:
            t = Timeout.start_new(timeout)
            try:
                alive = waiter.wait()
                if alive:
                    joinall(alive, raise_error=False)
            finally:
                t.cancel()
    else:
        core.active_event(_killall, greenlets, exception)


class LinkedExited(Exception):
    pass


class LinkedCompleted(LinkedExited):
    """Raised when a linked greenlet finishes the execution cleanly"""

    msg = "%r completed successfully"

    def __init__(self, source):
        assert source.ready(), source
        assert source.successful(), source
        LinkedExited.__init__(self, self.msg % source)


class LinkedKilled(LinkedCompleted):
    """Raised when a linked greenlet returns GreenletExit instance"""

    msg = "%r returned %s"

    def __init__(self, source):
        try:
            result = source.value.__class__.__name__
        except:
            result = str(source) or repr(source)
        LinkedExited.__init__(self, self.msg % (source, result))


def getLinkedCompleted(source):
    if isinstance(source.value, GreenletExit):
        return LinkedKilled(source)
    else:
        return LinkedCompleted(source)


class LinkedFailed(LinkedExited):
    """Raised when a linked greenlet dies because of unhandled exception"""

    msg = "%r failed with %s"

    def __init__(self, source):
        exception = source.exception
        try:
            excname = exception.__class__.__name__
        except:
            excname = str(exception) or repr(exception)
        LinkedExited.__init__(self, self.msg % (source, excname))


def getfuncname(func):
    if not hasattr(func, 'im_self'):
        try:
            funcname = func.__name__
        except AttributeError:
            pass
        else:
            if funcname != '<lambda>':
                return funcname
    return repr(func)


_NONE = Exception("Greenlet didn't even start")

