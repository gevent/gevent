# Copyright (c) 2009-2012 Denis Bilenko. See LICENSE for details.
"""Make the standard library cooperative."""
from __future__ import absolute_import
from __future__ import print_function
import sys

__all__ = ['patch_all',
           'patch_socket',
           'patch_ssl',
           'patch_os',
           'patch_time',
           'patch_select',
           'patch_thread',
           'patch_subprocess',
           'patch_sys',
           'patch_signal',
           # query functions
           'get_original',
           'is_module_patched',
           'is_object_patched', ]


if sys.version_info[0] >= 3:
    string_types = str,
    PY3 = True
else:
    import __builtin__
    string_types = __builtin__.basestring
    PY3 = False


# maps module name -> attribute name -> original item
# e.g. "time" -> "sleep" -> built-in function sleep
saved = {}


def is_module_patched(modname):
    """Check if a module has been replaced with a cooperative version."""
    return modname in saved


def is_object_patched(modname, objname):
    """Check if an object in a module has been replaced with a cooperative version."""
    return is_module_patched(modname) and objname in saved[modname]


def _get_original(name, items):
    d = saved.get(name, {})
    values = []
    module = None
    for item in items:
        if item in d:
            values.append(d[item])
        else:
            if module is None:
                module = __import__(name)
            values.append(getattr(module, item))
    return values


def get_original(mod_name, item_name):
    """Retrieve the original object from a module.

    If the object has not been patched, then that object will still be retrieved.

    :param item_name: A string or sequenc of strings naming the attribute(s) on the module
        ``mod_name`` to return.
    :return: The original value if a string was given for ``item_name`` or a sequence
        of original values if a sequence was passed.
    """
    if isinstance(item_name, string_types):
        return _get_original(mod_name, [item_name])[0]
    else:
        return _get_original(mod_name, item_name)


def patch_item(module, attr, newitem):
    NONE = object()
    olditem = getattr(module, attr, NONE)
    if olditem is not NONE:
        saved.setdefault(module.__name__, {}).setdefault(attr, olditem)
    setattr(module, attr, newitem)


def remove_item(module, attr):
    NONE = object()
    olditem = getattr(module, attr, NONE)
    if olditem is NONE:
        return
    saved.setdefault(module.__name__, {}).setdefault(attr, olditem)
    delattr(module, attr)


def patch_module(name, items=None):
    gevent_module = getattr(__import__('gevent.' + name), name)
    module_name = getattr(gevent_module, '__target__', name)
    module = __import__(module_name)
    if items is None:
        items = getattr(gevent_module, '__implements__', None)
        if items is None:
            raise AttributeError('%r does not have __implements__' % gevent_module)
    for attr in items:
        patch_item(module, attr, getattr(gevent_module, attr))


def _patch_sys_std(name):
    from gevent.fileobject import FileObjectThread
    orig = getattr(sys, name)
    if not isinstance(orig, FileObjectThread):
        patch_item(sys, name, FileObjectThread(orig))


def patch_sys(stdin=True, stdout=True, stderr=True):
    """Patch sys.std[in,out,err] to use a cooperative IO via a threadpool.

    This is relatively dangerous and can have unintended consequences such as hanging
    the process or `misinterpreting control keys`_ when ``input`` and ``raw_input``
    are used.

    This method does nothing on Python 3. The Python 3 interpreter wants to flush
    the TextIOWrapper objects that make up stderr/stdout at shutdown time, but
    using a threadpool at that time leads to a hang.

    .. _`misinterpreting control keys`: https://github.com/gevent/gevent/issues/274
    """
    # test__issue6.py demonstrates the hang if these lines are removed;
    # strangely enough that test passes even without monkey-patching sys
    if PY3:
        return

    if stdin:
        _patch_sys_std('stdin')
    if stdout:
        _patch_sys_std('stdout')
    if stderr:
        _patch_sys_std('stderr')


def patch_os():
    """
    Replace :func:`os.fork` with :func:`gevent.fork`, and, on POSIX,
    :func:`os.waitpid` with :func:`gevent.os.waitpid` (if the
    environment variable ``GEVENT_NOWAITPID`` is not defined). Does
    nothing if fork is not available.
    """
    patch_module('os')


def patch_time():
    """Replace :func:`time.sleep` with :func:`gevent.sleep`."""
    from gevent.hub import sleep
    import time
    patch_item(time, 'sleep', sleep)


def _patch_existing_locks(threading):
    if len(list(threading.enumerate())) != 1:
        return
    try:
        tid = threading.get_ident()
    except AttributeError:
        tid = threading._get_ident()
    rlock_type = type(threading.RLock())
    try:
        import importlib._bootstrap
    except ImportError:
        class _ModuleLock(object):
            pass
    else:
        _ModuleLock = importlib._bootstrap._ModuleLock
    # It might be possible to walk up all the existing stack frames to find
    # locked objects...at least if they use `with`. To be sure, we look at every object
    # Since we're supposed to be done very early in the process, there shouldn't be
    # too many.

    # By definition there's only one thread running, so the various
    # owner attributes were the old (native) thread id. Make it our
    # current greenlet id so that when it wants to unlock and compare
    # self.__owner with _get_ident(), they match.
    gc = __import__('gc')
    for o in gc.get_objects():
        if isinstance(o, rlock_type):
            if hasattr(o, '_owner'): # Py3
                if o._owner is not None:
                    o._owner = tid
            else:
                if o._RLock__owner is not None:
                    o._RLock__owner = tid
        elif isinstance(o, _ModuleLock):
            if o.owner is not None:
                o.owner = tid


def patch_thread(threading=True, _threading_local=True, Event=False, logging=True,
                 existing_locks=True):
    """Replace the standard :mod:`thread` module to make it greenlet-based.

    - If *threading* is true (the default), also patch ``threading``.
    - If *_threading_local* is true (the default), also patch ``_threading_local.local``.
    - If *logging* is True (the default), also patch locks taken if the logging module has
      been configured.
    - If *existing_locks* is True (the default), and the process is still single threaded,
      make sure than any :class:`threading.RLock` (and, under Python 3, :class:`importlib._bootstrap._ModuleLock`)
      instances that are currently locked can be properly unlocked.
    """
    patch_module('thread')
    if threading:
        patch_module('threading')
        threading = __import__('threading')
        if Event:
            from gevent.event import Event
            patch_item(threading, 'Event', Event)

        if existing_locks:
            _patch_existing_locks(threading)

        if logging and 'logging' in sys.modules:
            logging = __import__('logging')
            patch_item(logging, '_lock', threading.RLock())
            for wr in logging._handlerList:
                # In py26, these are actual handlers, not weakrefs
                handler = wr() if callable(wr) else wr
                if handler is None:
                    continue
                if not hasattr(handler, 'lock'):
                    raise TypeError("Unknown/unsupported handler %r" % handler)
                handler.lock = threading.RLock()

    if _threading_local:
        _threading_local = __import__('_threading_local')
        from gevent.local import local
        patch_item(_threading_local, 'local', local)

    if sys.version_info[:2] >= (3, 4):

        # Issue 18808 changes the nature of Thread.join() to use
        # locks. This means that a greenlet spawned in the main thread
        # (which is already running) cannot wait for the main thread---it
        # hangs forever. We patch around this if possible. See also
        # gevent.threading.
        threading = __import__('threading')
        greenlet = __import__('greenlet')
        if threading.current_thread() == threading.main_thread():
            main_thread = threading.main_thread()
            _greenlet = main_thread._greenlet = greenlet.getcurrent()
            from gevent.hub import sleep

            def join(timeout=None):
                if threading.current_thread() is main_thread:
                    raise RuntimeError("Cannot join current thread")
                if _greenlet.dead or not main_thread.is_alive():
                    return
                elif timeout:
                    raise ValueError("Cannot use a timeout to join the main thread")
                    # XXX: Make that work
                else:
                    while main_thread.is_alive():
                        sleep(0.01)

            main_thread.join = join
        else:
            # TODO: Can we use warnings here or does that mess up monkey patching?
            print("Monkey-patching not on the main thread; "
                  "threading.main_thread().join() will hang from a greenlet",
                  file=sys.stderr)


def patch_socket(dns=True, aggressive=True):
    """Replace the standard socket object with gevent's cooperative sockets.

    If ``dns`` is true, also patch dns functions in :mod:`socket`.
    """
    from gevent import socket
    # Note: although it seems like it's not strictly necessary to monkey patch 'create_connection',
    # it's better to do it. If 'create_connection' was not monkey patched, but the rest of socket module
    # was, create_connection would still use "green" getaddrinfo and "green" socket.
    # However, because gevent.socket.socket.connect is a Python function, the exception raised by it causes
    # _socket object to be referenced by the frame, thus causing the next invocation of bind(source_address) to fail.
    if dns:
        items = socket.__implements__
    else:
        items = set(socket.__implements__) - set(socket.__dns__)
    patch_module('socket', items=items)
    if aggressive:
        if 'ssl' not in socket.__implements__:
            remove_item(socket, 'ssl')


def patch_dns():
    """Replace DNS functions in :mod:`socket` with cooperative versions.

    This is only useful if :func:`patch_socket` has been called and is done automatically
    by that method if requested.
    """
    from gevent import socket
    patch_module('socket', items=socket.__dns__)


def patch_ssl():
    """Replace SSLSocket object and socket wrapping functions in :mod:`ssl` with cooperative versions.

    This is only useful if :func:`patch_socket` has been called.
    """
    patch_module('ssl')


def patch_select(aggressive=True):
    """Replace :func:`select.select` with :func:`gevent.select.select`.

    If ``aggressive`` is true (the default), also remove other blocking functions from :mod:`select`
    and (on Python 3.4 and above) :mod:`selectors`.
    """
    patch_module('select')
    if aggressive:
        select = __import__('select')
        # since these are blocking we're removing them here. This makes some other
        # modules (e.g. asyncore)  non-blocking, as they use select that we provide
        # when none of these are available.
        remove_item(select, 'epoll')
        remove_item(select, 'kqueue')
        remove_item(select, 'kevent')

    if sys.version_info[:2] >= (3, 4):
        # Python 3 wants to use `select.select` as a member function,
        # leading to this error in selectors.py (because gevent.select.select is
        # not a builtin and doesn't get the magic auto-static that they do)
        #    r, w, _ = self._select(self._readers, self._writers, [], timeout)
        #    TypeError: select() takes from 3 to 4 positional arguments but 5 were given
        select = __import__('select')
        selectors = __import__('selectors')
        if selectors.SelectSelector._select is select.select:
            def _select(self, *args, **kwargs):
                return select.select(*args, **kwargs)
            selectors.SelectSelector._select = _select

        if aggressive:
            # If `selectors` had already been imported before we removed
            # select.epoll|kqueue, these may have been defined in terms
            # of those functions. They'll fail at runtime.
            remove_item(selectors, 'EpollSelector')
            remove_item(selectors, 'KqueueSelector')
            selectors.DefaultSelector = selectors.SelectSelector


def patch_subprocess():
    """Replace :func:`subprocess.call`, :func:`subprocess.check_call`,
    :func:`subprocess.check_output` and :func:`subprocess.Popen` with cooperative versions."""
    patch_module('subprocess')


def patch_builtins():
    """Make the builtin __import__ function greenlet safe under Python 2"""
    # https://github.com/gevent/gevent/issues/108
    # Note that this is only needed in Python 2; under Python 3 (at least the versions
    # we support) import locks are not global, they're per-module.
    if sys.version_info[:2] < (3, 3):
        patch_module('builtins')


def patch_signal():
    """
    Make the signal.signal function work with a monkey-patched os.

    .. seealso:: :mod:`gevent.signal`
    """
    patch_module("signal")


def patch_all(socket=True, dns=True, time=True, select=True, thread=True, os=True, ssl=True, httplib=False,
              subprocess=True, sys=False, aggressive=True, Event=False,
              builtins=True, signal=True):
    """Do all of the default monkey patching (calls every other applicable function in this module)."""
    # order is important
    if os:
        patch_os()
    if time:
        patch_time()
    if thread:
        patch_thread(Event=Event)
    # sys must be patched after thread. in other cases threading._shutdown will be
    # initiated to _MainThread with real thread ident
    if sys:
        patch_sys()
    if socket:
        patch_socket(dns=dns, aggressive=aggressive)
    if select:
        patch_select(aggressive=aggressive)
    if ssl:
        patch_ssl()
    if httplib:
        raise ValueError('gevent.httplib is no longer provided, httplib must be False')
    if subprocess:
        patch_subprocess()
    if builtins:
        patch_builtins()
    if signal:
        patch_signal()


if __name__ == '__main__':
    from inspect import getargspec
    patch_all_args = getargspec(patch_all)[0]
    modules = [x for x in patch_all_args if 'patch_' + x in globals()]
    script_help = """gevent.monkey - monkey patch the standard modules to use gevent.

USAGE: python -m gevent.monkey [MONKEY OPTIONS] script [SCRIPT OPTIONS]

If no OPTIONS present, monkey patches all the modules it can patch.
You can exclude a module with --no-module, e.g. --no-thread. You can
specify a module to patch with --module, e.g. --socket. In the latter
case only the modules specified on the command line will be patched.

MONKEY OPTIONS: --verbose %s""" % ', '.join('--[no-]%s' % m for m in modules)
    args = {}
    argv = sys.argv[1:]
    verbose = False
    while argv and argv[0].startswith('--'):
        option = argv[0][2:]
        if option == 'verbose':
            verbose = True
        elif option.startswith('no-') and option.replace('no-', '') in patch_all_args:
            args[option[3:]] = False
        elif option in patch_all_args:
            args[option] = True
            if option in modules:
                for module in modules:
                    args.setdefault(module, False)
        else:
            sys.exit(script_help + '\n\n' + 'Cannot patch %r' % option)
        del argv[0]
        # TODO: break on --
    if verbose:
        import pprint
        import os
        print('gevent.monkey.patch_all(%s)' % ', '.join('%s=%s' % item for item in args.items()))
        print('sys.version=%s' % (sys.version.strip().replace('\n', ' '), ))
        print('sys.path=%s' % pprint.pformat(sys.path))
        print('sys.modules=%s' % pprint.pformat(sorted(sys.modules.keys())))
        print('cwd=%s' % os.getcwd())

    patch_all(**args)
    if argv:
        sys.argv = argv
        __package__ = None
        globals()['__file__'] = sys.argv[0]  # issue #302
        with open(sys.argv[0]) as f:
            exec(f.read())
    else:
        print(script_help)
