# Copyright (c) 2009-2011 Denis Bilenko. See LICENSE for details.
"""Basic synchronization primitives: Event and AsyncResult"""

import sys
from gevent.hub import get_hub, getcurrent, _NONE, PY3, reraise
from gevent.hub import InvalidSwitchError
from gevent.timeout import Timeout
from gevent._tblib import dump_traceback, load_traceback
from collections import deque
if PY3:
    xrange = range

__all__ = ['Event', 'AsyncResult']


class Event(object):
    """A synchronization primitive that allows one greenlet to wake up one or more others.
    It has the same interface as :class:`threading.Event` but works across greenlets.

    An event object manages an internal flag that can be set to true with the
    :meth:`set` method and reset to false with the :meth:`clear` method. The :meth:`wait` method
    blocks until the flag is true.
    """

    def __init__(self):
        self._links = set()
        self._todo = set()
        self._flag = False
        self.hub = get_hub()
        self._notifier = None

    def __str__(self):
        return '<%s %s _links[%s]>' % (self.__class__.__name__, (self._flag and 'set') or 'clear', len(self._links))

    def is_set(self):
        """Return true if and only if the internal flag is true."""
        return self._flag

    isSet = is_set  # makes it a better drop-in replacement for threading.Event
    ready = is_set  # makes it compatible with AsyncResult and Greenlet (for example in wait())

    def set(self):
        """
        Set the internal flag to true.

        All greenlets waiting for it to become true are awakened.
        Greenlets that call :meth:`wait` once the flag is true will
        not block at all.
        """
        self._flag = True
        self._todo.update(self._links)
        if self._todo and not self._notifier:
            self._notifier = self.hub.loop.run_callback(self._notify_links)

    def clear(self):
        """
        Reset the internal flag to false.

        Subsequently, threads calling :meth:`wait` will block until
        :meth:`set` is called to set the internal flag to true again.
        """
        self._flag = False

    def wait(self, timeout=None):
        """Block until the internal flag is true.

        If the internal flag is true on entry, return immediately. Otherwise,
        block until another thread calls :meth:`set` to set the flag to true,
        or until the optional timeout occurs.

        When the *timeout* argument is present and not ``None``, it should be a
        floating point number specifying a timeout for the operation in seconds
        (or fractions thereof).

        :return: The value of the internal flag (``True`` or ``False``).
           (If no timeout was given, the only possible return value is ``True``.)
        """
        if self._flag:
            return self._flag

        switch = getcurrent().switch
        self.rawlink(switch)
        try:
            timer = Timeout.start_new(timeout)
            try:
                try:
                    result = self.hub.switch()
                    if result is not self:
                        raise InvalidSwitchError('Invalid switch into Event.wait(): %r' % (result, ))
                except Timeout as ex:
                    if ex is not timer:
                        raise
            finally:
                timer.cancel()
        finally:
            self.unlink(switch)
        return self._flag

    def rawlink(self, callback):
        """Register a callback to call when the internal flag is set to true.

        *callback* will be called in the :class:`Hub <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.add(callback)
        if self._flag and not self._notifier:
            self._todo.add(callback)
            self._notifier = self.hub.loop.run_callback(self._notify_links)

    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        try:
            self._links.remove(callback)
        except ValueError:
            pass

    def _notify_links(self):
        while self._todo:
            link = self._todo.pop()
            if link in self._links:  # check that link was not notified yet and was not removed by the client
                try:
                    link(self)
                except:
                    self.hub.handle_error((link, self), *sys.exc_info())

    def _reset_internal_locks(self):
        # for compatibility with threading.Event (only in case of patch_all(Event=True), by default Event is not patched)
        #  Exception AttributeError: AttributeError("'Event' object has no attribute '_reset_internal_locks'",)
        # in <module 'threading' from '/usr/lib/python2.7/threading.pyc'> ignored
        pass


class AsyncResult(object):
    """A one-time event that stores a value or an exception.

    Like :class:`Event` it wakes up all the waiters when :meth:`set` or :meth:`set_exception`
    is called. Waiters may receive the passed value or exception by calling :meth:`get`
    instead of :meth:`wait`. An :class:`AsyncResult` instance cannot be reset.

    To pass a value call :meth:`set`. Calls to :meth:`get` (those that are currently blocking as well as
    those made in the future) will return the value:

        >>> result = AsyncResult()
        >>> result.set(100)
        >>> result.get()
        100

    To pass an exception call :meth:`set_exception`. This will cause :meth:`get` to raise that exception:

        >>> result = AsyncResult()
        >>> result.set_exception(RuntimeError('failure'))
        >>> result.get()
        Traceback (most recent call last):
         ...
        RuntimeError: failure

    :class:`AsyncResult` implements :meth:`__call__` and thus can be used as :meth:`link` target:

        >>> import gevent
        >>> result = AsyncResult()
        >>> gevent.spawn(lambda : 1/0).link(result)
        >>> try:
        ...     result.get()
        ... except ZeroDivisionError:
        ...     print('ZeroDivisionError')
        ZeroDivisionError
    """

    _value = _NONE
    _exc_info = ()
    _notifier = None

    def __init__(self):
        self._links = deque()
        self.hub = get_hub()

    @property
    def _exception(self):
        return self._exc_info[1] if self._exc_info else _NONE

    @property
    def value(self):
        """
        Holds the value passed to :meth:`set` if :meth:`set` was called. Otherwise,
        ``None``
        """
        return self._value if self._value is not _NONE else None

    @property
    def exc_info(self):
        """
        The three-tuple of exception information if :meth:`set_exception` was called.
        """
        if self._exc_info:
            return (self._exc_info[0], self._exc_info[1], load_traceback(self._exc_info[2]))
        return ()

    def __str__(self):
        result = '<%s ' % (self.__class__.__name__, )
        if self.value is not None or self._exception is not _NONE:
            result += 'value=%r ' % self.value
        if self._exception is not None and self._exception is not _NONE:
            result += 'exception=%r ' % self._exception
        if self._exception is _NONE:
            result += 'unset '
        return result + ' _links[%s]>' % len(self._links)

    def ready(self):
        """Return true if and only if it holds a value or an exception"""
        return self._exc_info or self._value is not _NONE

    def successful(self):
        """Return true if and only if it is ready and holds a value"""
        return self._value is not _NONE

    @property
    def exception(self):
        """Holds the exception instance passed to :meth:`set_exception` if :meth:`set_exception` was called.
        Otherwise ``None``."""
        if self._exc_info:
            return self._exc_info[1]

    def set(self, value=None):
        """Store the value and wake up any waiters.

        All greenlets blocking on :meth:`get` or :meth:`wait` are awakened.
        Subsequent calls to :meth:`wait` and :meth:`get` will not block at all.
        """
        self._value = value
        if self._links and not self._notifier:
            self._notifier = self.hub.loop.run_callback(self._notify_links)

    def set_exception(self, exception, exc_info=None):
        """Store the exception and wake up any waiters.

        All greenlets blocking on :meth:`get` or :meth:`wait` are awakened.
        Subsequent calls to :meth:`wait` and :meth:`get` will not block at all.

        :keyword tuple exc_info: If given, a standard three-tuple of type, value, :class:`traceback`
            as returned by :func:`sys.exc_info`. This will be used when the exception
            is re-raised to propagate the correct traceback.
        """
        if exc_info:
            self._exc_info = (exc_info[0], exc_info[1], dump_traceback(exc_info[2]))
        else:
            self._exc_info = (type(exception), exception, dump_traceback(None))

        if self._links and not self._notifier:
            self._notifier = self.hub.loop.run_callback(self._notify_links)

    def _raise_exception(self):
        reraise(*self.exc_info)

    def get(self, block=True, timeout=None):
        """Return the stored value or raise the exception.

        If this instance already holds a value or an exception, return  or raise it immediatelly.
        Otherwise, block until another greenlet calls :meth:`set` or :meth:`set_exception` or
        until the optional timeout occurs.

        When the *timeout* argument is present and not ``None``, it should be a
        floating point number specifying a timeout for the operation in seconds
        (or fractions thereof).

        :keyword bool block: If set to ``False`` and this instance is not ready,
            immediately raise a :class:`Timeout` exception.
        """
        if self._value is not _NONE:
            return self._value
        if self._exc_info:
            return self._raise_exception()

        if not block:
            # Not ready and not blocking, so immediately timeout
            raise Timeout()

        switch = getcurrent().switch
        self.rawlink(switch)
        try:
            timer = Timeout.start_new(timeout)
            try:
                result = self.hub.switch()
                if result is not self:
                    raise InvalidSwitchError('Invalid switch into AsyncResult.get(): %r' % (result, ))
            finally:
                timer.cancel()
        except:
            self.unlink(switch)
            raise

        # by definition we are now ready
        return self.get(block=False)

    def get_nowait(self):
        """
        Return the value or raise the exception without blocking.

        If this object is not yet :meth:`ready <ready>`, raise
        :class:`gevent.Timeout` immediately.
        """
        return self.get(block=False)

    def wait(self, timeout=None):
        """Block until the instance is ready.

        If this instance already holds a value, it is returned immediately. If this
        instance already holds an exception, ``None`` is returned immediately.

        Otherwise, block until another greenlet calls :meth:`set` or :meth:`set_exception`
        (at which point either the value or ``None`` will be returned, respectively),
        or until the optional timeout expires (at which point ``None`` will also be
        returned).

        When the *timeout* argument is present and not ``None``, it should be a
        floating point number specifying a timeout for the operation in seconds
        (or fractions thereof).

        .. note:: If a timeout is given and expires, ``None`` will be returned
            (no timeout exception will be raised).

        """
        if self.ready():
            return self.value

        switch = getcurrent().switch
        self.rawlink(switch)
        try:
            timer = Timeout.start_new(timeout)
            try:
                result = self.hub.switch()
                if result is not self:
                    raise InvalidSwitchError('Invalid switch into AsyncResult.wait(): %r' % (result, ))
            finally:
                timer.cancel()
        except Timeout as exc:
            self.unlink(switch)
            if exc is not timer:
                raise
        except:
            self.unlink(switch)
            raise
        # not calling unlink() in non-exception case, because if switch()
        # finished normally, link was already removed in _notify_links
        return self.value

    def _notify_links(self):
        while self._links:
            link = self._links.popleft()
            try:
                link(self)
            except:
                self.hub.handle_error((link, self), *sys.exc_info())

    def rawlink(self, callback):
        """Register a callback to call when a value or an exception is set.

        *callback* will be called in the :class:`Hub <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        if not callable(callback):
            raise TypeError('Expected callable: %r' % (callback, ))
        self._links.append(callback)
        if self.ready() and not self._notifier:
            self._notifier = self.hub.loop.run_callback(self._notify_links)

    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        try:
            self._links.remove(callback)
        except ValueError:
            pass

    # link protocol
    def __call__(self, source):
        if source.successful():
            self.set(source.value)
        else:
            self.set_exception(source.exception, getattr(source, 'exc_info', None))
