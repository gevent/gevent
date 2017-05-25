# Copyright (c) 2009-2012 Denis Bilenko. See LICENSE for details.
# pylint: disable=redefined-outer-name
"""
Make the standard library cooperative.

Patching
========

The primary purpose of this module is to carefully patch, in place,
portions of the standard library with gevent-friendly functions that
behave in the same way as the original (at least as closely as possible).

The primary interface to this is the :func:`patch_all` function, which
performs all the available patches. It accepts arguments to limit the
patching to certain modules, but most programs **should** use the
default values as they receive the most wide-spread testing, and some monkey
patches have dependencies on others.

Patching **should be done as early as possible** in the lifecycle of the
program. For example, the main module (the one that tests against
``__main__`` or is otherwise the first imported) should begin with
this code, ideally before any other imports::

    from gevent import monkey
    monkey.patch_all()

.. tip::

    Some frameworks, such as gunicorn, handle monkey-patching for you.
    Check their documentation to be sure.

Querying
--------

Sometimes it is helpful to know if objects have been monkey-patched, and in
advanced cases even to have access to the original standard library functions. This
module provides functions for that purpose.

- :func:`is_module_patched`
- :func:`is_object_patched`
- :func:`get_original`

Use as a module
===============

Sometimes it is useful to run existing python scripts or modules that
were not built to be gevent aware under gevent. To do so, this module
can be run as the main module, passing the script and its arguments.
For details, see the :func:`main` function.

Functions
=========
"""
from __future__ import absolute_import
from __future__ import print_function
import sys

__all__ = [
    'patch_all',
    'patch_builtins',
    'patch_dns',
    'patch_os',
    'patch_select',
    'patch_signal',
    'patch_socket',
    'patch_ssl',
    'patch_subprocess',
    'patch_sys',
    'patch_thread',
    'patch_time',
    # query functions
    'get_original',
    'is_module_patched',
    'is_object_patched',
    # module functions
    'main',
]


if sys.version_info[0] >= 3:
    string_types = (str,)
    PY3 = True
else:
    import __builtin__ # pylint:disable=import-error
    string_types = (__builtin__.basestring,)
    PY3 = False

WIN = sys.platform.startswith("win")

# maps module name -> {attribute name: original item}
# e.g. "time" -> {"sleep": built-in function sleep}
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

    :param item_name: A string or sequence of strings naming the attribute(s) on the module
        ``mod_name`` to return.
    :return: The original value if a string was given for ``item_name`` or a sequence
        of original values if a sequence was passed.
    """
    if isinstance(item_name, string_types):
        return _get_original(mod_name, [item_name])[0]
    return _get_original(mod_name, item_name)

_NONE = object()


def patch_item(module, attr, newitem):
    olditem = getattr(module, attr, _NONE)
    if olditem is not _NONE:
        saved.setdefault(module.__name__, {}).setdefault(attr, olditem)
    setattr(module, attr, newitem)


def remove_item(module, attr):
    olditem = getattr(module, attr, _NONE)
    if olditem is _NONE:
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
    return module


def _queue_warning(message, _warnings):
    # Queues a warning to show after the monkey-patching process is all done.
    # Done this way to avoid extra imports during the process itself, just
    # in case. If we're calling a function one-off (unusual) go ahead and do it
    if _warnings is None:
        _process_warnings([message])
    else:
        _warnings.append(message)


def _process_warnings(_warnings):
    import warnings
    for warning in _warnings:
        warnings.warn(warning, RuntimeWarning, stacklevel=3)


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

    .. caution:: This method must be used with :func:`patch_signal` to have proper SIGCHLD
         handling and thus correct results from ``waitpid``.
         :func:`patch_all` calls both by default.

    .. caution:: For SIGCHLD handling to work correctly, the event loop must run.
         The easiest way to help ensure this is to use :func:`patch_all`.
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
        _ModuleLock = importlib._bootstrap._ModuleLock # python 2 pylint: disable=no-member
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
                 existing_locks=True,
                 _warnings=None):
    """
    Replace the standard :mod:`thread` module to make it greenlet-based.

    - If *threading* is true (the default), also patch ``threading``.
    - If *_threading_local* is true (the default), also patch ``_threading_local.local``.
    - If *logging* is True (the default), also patch locks taken if the logging module has
      been configured.
    - If *existing_locks* is True (the default), and the process is still single threaded,
      make sure than any :class:`threading.RLock` (and, under Python 3, :class:`importlib._bootstrap._ModuleLock`)
      instances that are currently locked can be properly unlocked.

    .. caution::
        Monkey-patching :mod:`thread` and using
        :class:`multiprocessing.Queue` or
        :class:`concurrent.futures.ProcessPoolExecutor` (which uses a
        ``Queue``) will hang the process.

    .. versionchanged:: 1.1b1
        Add *logging* and *existing_locks* params.
    """
    # XXX: Simplify
    # pylint:disable=too-many-branches,too-many-locals

    # Description of the hang:
    # There is an incompatibility with patching 'thread' and the 'multiprocessing' module:
    # The problem is that multiprocessing.queues.Queue uses a half-duplex multiprocessing.Pipe,
    # which is implemented with os.pipe() and _multiprocessing.Connection. os.pipe isn't patched
    # by gevent, as it returns just a fileno. _multiprocessing.Connection is an internal implementation
    # class implemented in C, which exposes a 'poll(timeout)' method; under the covers, this issues a
    # (blocking) select() call: hence the need for a real thread. Except for that method, we could
    # almost replace Connection with gevent.fileobject.SocketAdapter, plus a trivial
    # patch to os.pipe (below). Sigh, so close. (With a little work, we could replicate that method)

    # import os
    # import fcntl
    # os_pipe = os.pipe
    # def _pipe():
    #   r, w = os_pipe()
    #   fcntl.fcntl(r, fcntl.F_SETFL, os.O_NONBLOCK)
    #   fcntl.fcntl(w, fcntl.F_SETFL, os.O_NONBLOCK)
    #   return r, w
    # os.pipe = _pipe

    # The 'threading' module copies some attributes from the
    # thread module the first time it is imported. If we patch 'thread'
    # before that happens, then we store the wrong values in 'saved',
    # So if we're going to patch threading, we either need to import it
    # before we patch thread, or manually clean up the attributes that
    # are in trouble. The latter is tricky because of the different names
    # on different versions.
    if threading:
        threading_mod = __import__('threading')
        # Capture the *real* current thread object before
        # we start returning DummyThread objects, for comparison
        # to the main thread.
        orig_current_thread = threading_mod.current_thread()
    else:
        threading_mod = None
        orig_current_thread = None

    patch_module('thread')

    if threading:
        patch_module('threading')

        if Event:
            from gevent.event import Event
            patch_item(threading_mod, 'Event', Event)

        if existing_locks:
            _patch_existing_locks(threading_mod)

        if logging and 'logging' in sys.modules:
            logging = __import__('logging')
            patch_item(logging, '_lock', threading_mod.RLock())
            for wr in logging._handlerList:
                # In py26, these are actual handlers, not weakrefs
                handler = wr() if callable(wr) else wr
                if handler is None:
                    continue
                if not hasattr(handler, 'lock'):
                    raise TypeError("Unknown/unsupported handler %r" % handler)
                handler.lock = threading_mod.RLock()

    if _threading_local:
        _threading_local = __import__('_threading_local')
        from gevent.local import local
        patch_item(_threading_local, 'local', local)

    def make_join_func(thread, thread_greenlet):
        from gevent.hub import sleep
        from time import time

        def join(timeout=None):
            end = None
            if threading_mod.current_thread() is thread:
                raise RuntimeError("Cannot join current thread")
            if thread_greenlet is not None and thread_greenlet.dead:
                return
            if not thread.is_alive():
                return

            if timeout:
                end = time() + timeout

            while thread.is_alive():
                if end is not None and time() > end:
                    return
                sleep(0.01)
        return join

    if threading:
        from gevent.threading import main_native_thread

        for thread in threading_mod._active.values():
            if thread == main_native_thread():
                continue
            thread.join = make_join_func(thread, None)

    if sys.version_info[:2] >= (3, 4):

        # Issue 18808 changes the nature of Thread.join() to use
        # locks. This means that a greenlet spawned in the main thread
        # (which is already running) cannot wait for the main thread---it
        # hangs forever. We patch around this if possible. See also
        # gevent.threading.
        greenlet = __import__('greenlet')

        if orig_current_thread == threading_mod.main_thread():
            main_thread = threading_mod.main_thread()
            _greenlet = main_thread._greenlet = greenlet.getcurrent()

            main_thread.join = make_join_func(main_thread, _greenlet)

            # Patch up the ident of the main thread to match. This
            # matters if threading was imported before monkey-patching
            # thread
            oldid = main_thread.ident
            main_thread._ident = threading_mod.get_ident()
            if oldid in threading_mod._active:
                threading_mod._active[main_thread.ident] = threading_mod._active[oldid]
            if oldid != main_thread.ident:
                del threading_mod._active[oldid]
        else:
            _queue_warning("Monkey-patching not on the main thread; "
                           "threading.main_thread().join() will hang from a greenlet",
                           _warnings)


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
        items = socket.__implements__ # pylint:disable=no-member
    else:
        items = set(socket.__implements__) - set(socket.__dns__) # pylint:disable=no-member
    patch_module('socket', items=items)
    if aggressive:
        if 'ssl' not in socket.__implements__: # pylint:disable=no-member
            remove_item(socket, 'ssl')


def patch_dns():
    """Replace DNS functions in :mod:`socket` with cooperative versions.

    This is only useful if :func:`patch_socket` has been called and is done automatically
    by that method if requested.
    """
    from gevent import socket
    patch_module('socket', items=socket.__dns__) # pylint:disable=no-member


def patch_ssl():
    """Replace SSLSocket object and socket wrapping functions in :mod:`ssl` with cooperative versions.

    This is only useful if :func:`patch_socket` has been called.
    """
    patch_module('ssl')


def patch_select(aggressive=True):
    """
    Replace :func:`select.select` with :func:`gevent.select.select`
    and :func:`select.poll` with :class:`gevent.select.poll` (where available).

    If ``aggressive`` is true (the default), also remove other
    blocking functions from :mod:`select` and (on Python 3.4 and
    above) :mod:`selectors`:

    - :func:`select.epoll`
    - :func:`select.kqueue`
    - :func:`select.kevent`
    - :func:`select.devpoll` (Python 3.5+)
    - :class:`selectors.EpollSelector`
    - :class:`selectors.KqueueSelector`
    - :class:`selectors.DevpollSelector` (Python 3.5+)
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
        remove_item(select, 'devpoll')

    if sys.version_info[:2] >= (3, 4):
        # Python 3 wants to use `select.select` as a member function,
        # leading to this error in selectors.py (because gevent.select.select is
        # not a builtin and doesn't get the magic auto-static that they do)
        #    r, w, _ = self._select(self._readers, self._writers, [], timeout)
        #    TypeError: select() takes from 3 to 4 positional arguments but 5 were given
        # Note that this obviously only happens if selectors was imported after we had patched
        # select; but there is a code path that leads to it being imported first (but now we've
        # patched select---so we can't compare them identically)
        select = __import__('select') # Should be gevent-patched now
        orig_select_select = get_original('select', 'select')
        assert select.select is not orig_select_select
        selectors = __import__('selectors')
        if selectors.SelectSelector._select in (select.select, orig_select_select):
            def _select(self, *args, **kwargs): # pylint:disable=unused-argument
                return select.select(*args, **kwargs)
            selectors.SelectSelector._select = _select
            _select._gevent_monkey = True

        if aggressive:
            # If `selectors` had already been imported before we removed
            # select.epoll|kqueue|devpoll, these may have been defined in terms
            # of those functions. They'll fail at runtime.
            remove_item(selectors, 'EpollSelector')
            remove_item(selectors, 'KqueueSelector')
            remove_item(selectors, 'DevpollSelector')
            selectors.DefaultSelector = selectors.SelectSelector


def patch_subprocess():
    """
    Replace :func:`subprocess.call`, :func:`subprocess.check_call`,
    :func:`subprocess.check_output` and :class:`subprocess.Popen` with
    :mod:`cooperative versions <gevent.subprocess>`.

    .. note::
       On Windows under Python 3, the API support may not completely match
       the standard library.

    """
    patch_module('subprocess')


def patch_builtins():
    """
    Make the builtin __import__ function `greenlet safe`_ under Python 2.

    .. note::
       This does nothing under Python 3 as it is not necessary. Python 3 features
       improved import locks that are per-module, not global.

    .. _greenlet safe: https://github.com/gevent/gevent/issues/108

    """
    if sys.version_info[:2] < (3, 3):
        patch_module('builtins')


def patch_signal():
    """
    Make the signal.signal function work with a monkey-patched os.

    .. caution:: This method must be used with :func:`patch_os` to have proper SIGCHLD
         handling. :func:`patch_all` calls both by default.

    .. caution:: For proper SIGCHLD handling, you must yield to the event loop.
         Using :func:`patch_all` is the easiest way to ensure this.

    .. seealso:: :mod:`gevent.signal`
    """
    patch_module("signal")


def _check_repatching(**module_settings):
    _warnings = []
    key = '_gevent_saved_patch_all'
    if saved.get(key, module_settings) != module_settings:
        _queue_warning("Patching more than once will result in the union of all True"
                       " parameters being patched",
                       _warnings)

    first_time = key not in saved
    saved[key] = module_settings
    return _warnings, first_time


def patch_all(socket=True, dns=True, time=True, select=True, thread=True, os=True, ssl=True, httplib=False,
              subprocess=True, sys=False, aggressive=True, Event=False,
              builtins=True, signal=True):
    """
    Do all of the default monkey patching (calls every other applicable
    function in this module).

    .. versionchanged:: 1.1
       Issue a :mod:`warning <warnings>` if this function is called multiple times
       with different arguments. The second and subsequent calls will only add more
       patches, they can never remove existing patches by setting an argument to ``False``.
    .. versionchanged:: 1.1
       Issue a :mod:`warning <warnings>` if this function is called with ``os=False``
       and ``signal=True``. This will cause SIGCHLD handlers to not be called. This may
       be an error in the future.
    """
    # pylint:disable=too-many-locals,too-many-branches

    # Check to see if they're changing the patched list
    _warnings, first_time = _check_repatching(**locals())
    if not _warnings and not first_time:
        # Nothing to do, identical args to what we just
        # did
        return

    # order is important
    if os:
        patch_os()
    if time:
        patch_time()
    if thread:
        patch_thread(Event=Event, _warnings=_warnings)
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
        if not os:
            _queue_warning('Patching signal but not os will result in SIGCHLD handlers'
                           ' installed after this not being called and os.waitpid may not'
                           ' function correctly if gevent.subprocess is used. This may raise an'
                           ' error in the future.',
                           _warnings)
        patch_signal()

    _process_warnings(_warnings)


def main():
    args = {}
    argv = sys.argv[1:]
    verbose = False
    script_help, patch_all_args, modules = _get_script_help()
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
        assert __package__ is None
        globals()['__file__'] = sys.argv[0]  # issue #302
        globals()['__package__'] = None # issue #975: make script be its own package
        with open(sys.argv[0]) as f:
            # Be sure to exec in globals to avoid import pollution. Also #975.
            exec(f.read(), globals())
    else:
        print(script_help)


def _get_script_help():
    from inspect import getargspec
    patch_all_args = getargspec(patch_all)[0] # pylint:disable=deprecated-method
    modules = [x for x in patch_all_args if 'patch_' + x in globals()]
    script_help = """gevent.monkey - monkey patch the standard modules to use gevent.

USAGE: python -m gevent.monkey [MONKEY OPTIONS] script [SCRIPT OPTIONS]

If no OPTIONS present, monkey patches all the modules it can patch.
You can exclude a module with --no-module, e.g. --no-thread. You can
specify a module to patch with --module, e.g. --socket. In the latter
case only the modules specified on the command line will be patched.

MONKEY OPTIONS: --verbose %s""" % ', '.join('--[no-]%s' % m for m in modules)
    return script_help, patch_all_args, modules

main.__doc__ = _get_script_help()[0]

if __name__ == '__main__':
    main()
