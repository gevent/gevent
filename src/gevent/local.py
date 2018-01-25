"""
Greenlet-local objects.

This module is based on `_threading_local.py`__ from the standard
library of Python 3.4.

__ https://github.com/python/cpython/blob/3.4/Lib/_threading_local.py

Greenlet-local objects support the management of greenlet-local data.
If you have data that you want to be local to a greenlet, simply create
a greenlet-local object and use its attributes:

  >>> mydata = local()
  >>> mydata.number = 42
  >>> mydata.number
  42

You can also access the local-object's dictionary:

  >>> mydata.__dict__
  {'number': 42}
  >>> mydata.__dict__.setdefault('widgets', [])
  []
  >>> mydata.widgets
  []

What's important about greenlet-local objects is that their data are
local to a greenlet. If we access the data in a different greenlet:

  >>> log = []
  >>> def f():
  ...     items = list(mydata.__dict__.items())
  ...     items.sort()
  ...     log.append(items)
  ...     mydata.number = 11
  ...     log.append(mydata.number)
  >>> greenlet = gevent.spawn(f)
  >>> greenlet.join()
  >>> log
  [[], 11]

we get different data.  Furthermore, changes made in the other greenlet
don't affect data seen in this greenlet:

  >>> mydata.number
  42

Of course, values you get from a local object, including a __dict__
attribute, are for whatever greenlet was current at the time the
attribute was read.  For that reason, you generally don't want to save
these values across greenlets, as they apply only to the greenlet they
came from.

You can create custom local objects by subclassing the local class:

  >>> class MyLocal(local):
  ...     number = 2
  ...     initialized = False
  ...     def __init__(self, **kw):
  ...         if self.initialized:
  ...             raise SystemError('__init__ called too many times')
  ...         self.initialized = True
  ...         self.__dict__.update(kw)
  ...     def squared(self):
  ...         return self.number ** 2

This can be useful to support default values, methods and
initialization.  Note that if you define an __init__ method, it will be
called each time the local object is used in a separate greenlet.  This
is necessary to initialize each greenlet's dictionary.

Now if we create a local object:

  >>> mydata = MyLocal(color='red')

Now we have a default number:

  >>> mydata.number
  2

an initial color:

  >>> mydata.color
  'red'
  >>> del mydata.color

And a method that operates on the data:

  >>> mydata.squared()
  4

As before, we can access the data in a separate greenlet:

  >>> log = []
  >>> greenlet = gevent.spawn(f)
  >>> greenlet.join()
  >>> log
  [[('color', 'red'), ('initialized', True)], 11]

without affecting this greenlet's data:

  >>> mydata.number
  2
  >>> mydata.color
  Traceback (most recent call last):
  ...
  AttributeError: 'MyLocal' object has no attribute 'color'

Note that subclasses can define slots, but they are not greenlet
local. They are shared across greenlets::

  >>> class MyLocal(local):
  ...     __slots__ = 'number'

  >>> mydata = MyLocal()
  >>> mydata.number = 42
  >>> mydata.color = 'red'

So, the separate greenlet:

  >>> greenlet = gevent.spawn(f)
  >>> greenlet.join()

affects what we see:

  >>> mydata.number
  11

>>> del mydata

.. versionchanged:: 1.1a2
   Update the implementation to match Python 3.4 instead of Python 2.5.
   This results in locals being eligible for garbage collection as soon
   as their greenlet exits.

.. versionchanged:: 1.2.3
   Use a weak-reference to clear the greenlet link we establish in case
   the local object dies before the greenlet does.

.. versionchanged:: 1.3a1
   Implement the methods for attribute access directly, handling
   descriptors directly here. This allows removing the use of a lock
   and facilitates greatly improved performance.

.. versionchanged:: 1.3a1
   The ``__init__`` method of subclasses of ``local`` is no longer
   called with a lock held. CPython does not use such a lock in its
   native implementation. This could potentially show as a difference
   if code that uses multiple dependent attributes in ``__slots__``
   (which are shared across all greenlets) switches during ``__init__``.

"""
from __future__ import print_function

from copy import copy
from weakref import ref
from gevent.hub import getcurrent


__all__ = ["local"]


class _wrefdict(dict):
    """A dict that can be weak referenced"""

class _thread_deleted(object):
    __slots__ = ('idt', 'wrdicts')

    def __init__(self, idt, wrdicts):
        self.idt = idt
        self.wrdicts = wrdicts

    def __call__(self, _unused):
        dicts = self.wrdicts()
        if dicts:
            dicts.pop(self.idt, None)

class _local_deleted(object):
    __slots__ = ('key', 'wrthread', 'thread_deleted')

    def __init__(self, key, wrthread, thread_deleted):
        self.key = key
        self.wrthread = wrthread
        self.thread_deleted = thread_deleted

    def __call__(self, _unused):
        thread = self.wrthread()
        if thread is not None:
            try:
                unlink = thread.unlink
            except AttributeError:
                pass
            else:
                unlink(self.thread_deleted)
            del thread.__dict__[self.key]

class _localimpl(object):
    """A class managing thread-local dicts"""
    __slots__ = ('key', 'dicts', 'localargs', '__weakref__',)

    def __init__(self, args, kwargs):
        # The key used in the Thread objects' attribute dicts.
        # We keep it a string for speed but make it unlikely to clash with
        # a "real" attribute.
        self.key = '_threading_local._localimpl.' + str(id(self))
        # { id(Thread) -> (ref(Thread), thread-local dict) }
        self.dicts = _wrefdict()
        self.localargs = args, kwargs

        # We need to create the thread dict in anticipation of
        # __init__ being called, to make sure we don't call it
        # again ourselves. MUST do this before setting any attributes.
        _localimpl_create_dict(self)

# We use functions instead of methods so that they can be cdef'd in
# local.pxd; if they were cdef'd as methods, they would cause
# the creation of a pointer and a vtable. This happens
# even if we declare the class @cython.final. functions thus save memory overhead
# (but not pointer chasing overhead; the vtable isn't used when we declare
# the class final).

def _localimpl_get_dict(self):
    """Return the dict for the current thread. Raises KeyError if none
    defined."""
    thread = getcurrent()
    return self.dicts[id(thread)][1]

def _localimpl_create_dict(self):
    """Create a new dict for the current thread, and return it."""
    localdict = {}
    key = self.key
    thread = getcurrent()
    idt = id(thread)

    wrdicts = ref(self.dicts)

    # When the thread is deleted, remove the local dict.
    # Note that this is suboptimal if the thread object gets
    # caught in a reference loop. We would like to be called
    # as soon as the OS-level thread ends instead.

    # If we are working with a gevent.greenlet.Greenlet, we
    # can pro-actively clear out with a link, avoiding the
    # issue described above.Use rawlink to avoid spawning any
    # more greenlets.
    thread_deleted = _thread_deleted(idt, wrdicts)

    try:
        rawlink = thread.rawlink
    except AttributeError:
        wrthread = ref(thread, thread_deleted)
    else:
        rawlink(thread_deleted)
        wrthread = ref(thread)

    # When the localimpl is deleted, remove the thread attribute.
    local_deleted = _local_deleted(key, wrthread, thread_deleted)


    wrlocal = ref(self, local_deleted)
    thread.__dict__[key] = wrlocal

    self.dicts[idt] = wrthread, localdict
    return localdict


_marker = object()

def _local_get_dict(self):
    impl = self._local__impl
    try:
        dct = _localimpl_get_dict(impl)
    except KeyError:
        dct = _localimpl_create_dict(impl)
        args, kw = impl.localargs
        self.__init__(*args, **kw)
    return dct

class local(object):
    """
    An object whose attributes are greenlet-local.
    """
    __slots__ = ('_local__impl',)

    def __cinit__(self, *args, **kw):
        if args or kw:
            if type(self).__init__ == object.__init__:
                raise TypeError("Initialization arguments are not supported", args, kw)
        impl = _localimpl(args, kw)
        self._local__impl = impl # pylint:disable=attribute-defined-outside-init

    def __getattribute__(self, name): # pylint:disable=too-many-return-statements
        if name in ('__class__', '_local__impl', '__cinit__'):
            # The _local__impl and __cinit__ won't be hit by the
            # Cython version, if we've done things right. If we haven't,
            # they will be, and this will produce an error.
            return object.__getattribute__(self, name)

        dct = _local_get_dict(self)

        if name == '__dict__':
            return dct
        # If there's no possible way we can switch, because this
        # attribute is *not* found in the class where it might be a
        # data descriptor (property), and it *is* in the dict
        # then we don't need to swizzle the dict and take the lock.

        # We don't have to worry about people overriding __getattribute__
        # because if they did, the dict-swizzling would only last as
        # long as we were in here anyway.
        # Similarly, a __getattr__ will still be called by _oga() if needed
        # if it's not in the dict.

        type_self = type(self)
        # Optimization: If we're not subclassed, then
        # there can be no descriptors except for methods, which will
        # never need to use __dict__.
        if type_self is local:
            return dct[name] if name in dct else object.__getattribute__(self, name)

        # NOTE: If this is a descriptor, this will invoke its __get__.
        # A broken descriptor that doesn't return itself when called with
        # a None for the instance argument could mess us up here.
        # But this is faster than a loop over mro() checking each class __dict__
        # manually.
        type_attr = getattr(type_self, name, _marker)
        if name in dct:
            if type_attr is _marker:
                # If there is a dict value, and nothing in the type,
                # it can't possibly be a descriptor, so it is just returned.
                return dct[name]

            # It's in the type *and* in the dict. If the type value is
            # a data descriptor (defines __get__ *and* either __set__ or
            # __delete__), then the type wins. If it's a non-data descriptor
            # (defines just __get__), then the instance wins. If it's not a
            # descriptor at all (doesn't have __get__), the instance wins.
            # NOTE that the docs for descriptors say that these methods must be
            # defined on the *class* of the object in the type.
            type_type_attr = type(type_attr)
            if not hasattr(type_type_attr, '__get__'):
                # Entirely not a descriptor. Instance wins.
                return dct[name]
            if hasattr(type_type_attr, '__set__') or hasattr(type_type_attr, '__delete__'):
                # A data descriptor.
                # arbitrary code execution while these run. If they touch self again,
                # they'll call back into us and we'll repeat the dance.
                return type_type_attr.__get__(type_attr, self, type_self)
            # Last case is a non-data descriptor. Instance wins.
            return dct[name]
        elif type_attr is not _marker:
            # It's not in the dict at all. Is it in the type?
            type_type_attr = type(type_attr)
            if not hasattr(type_type_attr, '__get__'):
                # Not a descriptor, can't execute code
                return type_attr
            return type_type_attr.__get__(type_attr, self, type_self)

        # It wasn't in the dict and it wasn't in the type.
        # So the next step is to invoke type(self)__getattr__, if it
        # exists, otherwise raise an AttributeError.
        # we will invoke type(self).__getattr__ or raise an attribute error.
        if hasattr(type_self, '__getattr__'):
            return type_self.__getattr__(self, name)
        raise AttributeError("%r object has no attribute '%s'"
                             % (type_self.__name__, name))

    def __setattr__(self, name, value):
        if name == '__dict__':
            raise AttributeError(
                "%r object attribute '__dict__' is read-only"
                % type(self))

        if name == '_local__impl':
            object.__setattr__(self, '_local__impl', value)
            return

        dct = _local_get_dict(self)

        type_self = type(self)
        if type_self is local:
            # Optimization: If we're not subclassed, we can't
            # have data descriptors, so this goes right in the dict.
            dct[name] = value
            return

        type_attr = getattr(type_self, name, _marker)
        if type_attr is not _marker:
            type_type_attr = type(type_attr)
            if hasattr(type_type_attr, '__set__'):
                # A data descriptor, like a property or a slot.
                type_type_attr.__set__(type_attr, self, value)
                return
        # Otherwise it goes directly in the dict
        dct[name] = value

    def __delattr__(self, name):
        if name == '__dict__':
            raise AttributeError(
                "%r object attribute '__dict__' is read-only"
                % self.__class__.__name__)

        type_self = type(self)
        type_attr = getattr(type_self, name, _marker)
        if type_attr is not _marker:
            type_type_attr = type(type_attr)
            if hasattr(type_type_attr, '__delete__'):
                # A data descriptor, like a property or a slot.
                type_type_attr.__delete__(type_attr, self)
                return
        # Otherwise it goes directly in the dict

        # Begin inlined function _get_dict()
        dct = _local_get_dict(self)

        try:
            del dct[name]
        except KeyError:
            raise AttributeError(name)

    def __copy__(self):
        impl = self._local__impl

        d = _localimpl_get_dict(impl)
        duplicate = copy(d)

        cls = type(self)
        args, kw = impl.localargs
        instance = cls(*args, **kw)
        _local__copy_dict_from(instance, impl, duplicate)
        return instance

def _local__copy_dict_from(self, impl, duplicate):
    current = getcurrent()
    currentId = id(current)
    new_impl = self._local__impl
    assert new_impl is not impl
    tpl = new_impl.dicts[currentId]
    new_impl.dicts[currentId] = (tpl[0], duplicate)



# Cython doesn't let us use __new__, it requires
# __cinit__. But we need __new__ if we're not compiled
# (e.g., on PyPy). So we set it at runtime. Cython
# will raise an error if we're compiled.
def __new__(cls, *args, **kw):
    self = super(local, cls).__new__(cls)
    # We get the cls in *args for some reason
    # too when we do it this way....except on PyPy3, which does
    # not *unless* it's wrapped in a classmethod (which it is)
    self.__cinit__(*args[1:], **kw)
    return self

try:
    # PyPy2/3 and CPython handle adding a __new__ to the class
    # in different ways. In CPython and PyPy3, it must be wrapped with classmethod;
    # in PyPy2, it must not. In either case, the args that get passed to
    # it are stil wrong.
    import sys
    if hasattr(sys, 'pypy_version_info') and sys.version_info[:2] < (3, 0):
        local.__new__ = __new__
    else:
        local.__new__ = classmethod(__new__)
except TypeError:
    pass
finally:
    del sys
