# Copyright (c) 2009-2012 Denis Bilenko. See LICENSE for details.
"""Make the standard library cooperative."""
from __future__ import absolute_import
import sys
from sys import version_info

__all__ = ['patch_all',
           'patch_socket',
           'patch_ssl',
           'patch_os',
           'patch_time',
           'patch_select',
           'patch_thread',
           'patch_subprocess',
           'patch_sys']


# maps module name -> attribute name -> original item
# e.g. "time" -> "sleep" -> built-in function sleep
saved = {}


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


def get_original(name, item):
    if isinstance(item, basestring):
        return _get_original(name, [item])[0]
    else:
        return _get_original(name, item)


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
    _patch_sys_std('stdin')
    _patch_sys_std('stdout')
    _patch_sys_std('stderr')


def patch_os():
    """Replace :func:`os.fork` with :func:`gevent.fork`. Does nothing if fork is not available."""
    patch_module('os')


def patch_time():
    """Replace :func:`time.sleep` with :func:`gevent.sleep`."""
    from gevent.hub import sleep
    import time
    patch_item(time, 'sleep', sleep)


def patch_thread(threading=True, _threading_local=True, Event=False):
    """Replace the standard :mod:`thread` module to make it greenlet-based.
    If *threading* is true (the default), also patch ``threading``.
    If *_threading_local* is true (the default), also patch ``_threading_local.local``.
    """
    patch_module('thread')
    from gevent.local import local
    if threading:
        from gevent import thread as green_thread, getcurrent, Greenlet
        threading = __import__('threading')
        # QQQ Note, that importing threading results in get_hub() call.
        # QQQ Would prefer not to import threading at all if it's not used;
        # QQQ that should be possible with import hooks
        threading.local = local
        threading._start_new_thread = green_thread.start_new_thread
        threading._allocate_lock = green_thread.allocate_lock
        threading.Lock = green_thread.allocate_lock
        threading._get_ident = green_thread.get_ident
        from gevent.hub import sleep
        threading._sleep = sleep

        def cleanup_greenlet(g):
            with threading._active_limbo_lock:
                del threading._active[id(g)]

        class _GreenDummyThread(threading._DummyThread):
            # instances of this will cleanup its own entry
            # in ``threading._active``
            def __init__(self):
                threading._DummyThread.__init__(self)
                g = getcurrent()
                if isinstance(g, Greenlet):
                    g.link(cleanup_greenlet)

        def currentThread():
            try:
                return threading._active[threading._get_ident()]
            except KeyError:
                return _GreenDummyThread()
        threading.currentThread = currentThread
        threading.current_thread = currentThread

        if Event:
            from gevent.event import Event
            threading.Event = Event
    if _threading_local:
        _threading_local = __import__('_threading_local')
        _threading_local.local = local


def patch_socket(dns=True, aggressive=True):
    """Replace the standard socket object with gevent's cooperative sockets.

    If *dns* is true, also patch dns functions in :mod:`socket`.
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
    from gevent import socket
    patch_module('socket', items=socket.__dns__)


def patch_ssl():
    patch_module('ssl')


def patch_select(aggressive=True):
    """Replace :func:`select.select` with :func:`gevent.select.select`.

    If aggressive is true (the default), also remove other blocking functions the :mod:`select`.
    """
    patch_module('select')
    if aggressive:
        select = __import__('select')
        # since these are blocking we're removing them here. This makes some other
        # modules (e.g. asyncore)  non-blocking, as they use select that we provide
        # when none of these are available.
        remove_item(select, 'poll')
        remove_item(select, 'epoll')
        remove_item(select, 'kqueue')
        remove_item(select, 'kevent')


def patch_subprocess():
    patch_module('subprocess')


def patch_all(socket=True, dns=True, time=True, select=True, thread=True, os=True, ssl=True, httplib=False,
              subprocess=True, sys=False, aggressive=True, Event=False):
    """Do all of the default monkey patching (calls every other function in this module."""
    # order is important
    if sys:
        patch_sys()
    if os:
        patch_os()
    if time:
        patch_time()
    if thread:
        patch_thread(Event=Event)
    if socket:
        patch_socket(dns=dns, aggressive=aggressive)
    if select:
        patch_select(aggressive=aggressive)
    if ssl:
        if version_info[:2] > (2, 5):
            patch_ssl()
        else:
            try:
                patch_ssl()
            except ImportError:
                pass  # in Python 2.5, 'ssl' is a standalone package not included in stdlib
    if httplib:
        raise ValueError('gevent.httplib is no longer provided, httplib must be False')
    if subprocess:
        patch_subprocess()


if __name__ == '__main__':
    modules = [x.replace('patch_', '') for x in globals().keys() if x.startswith('patch_') and x != 'patch_all']
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
        elif option.startswith('no-') and option.replace('no-', '') in modules:
            args[option[3:]] = False
        elif option not in modules:
            args[option] = True
        else:
            sys.exit(script_help + '\n\n' + 'Cannot patch %r' % option)
        del argv[0]
        # TODO: break on --
    if verbose:
        import pprint
        import os
        print ('gevent.monkey.patch_all(%s)' % ', '.join('%s=%s' % item for item in args.items()))
        print ('sys.version=%s' % (sys.version.strip().replace('\n', ' '), ))
        print ('sys.path=%s' % pprint.pformat(sys.path))
        print ('sys.modules=%s' % pprint.pformat(sorted(sys.modules.keys())))
        print ('cwd=%s' % os.getcwd())

    patch_all(**args)
    if argv:
        sys.argv = argv
        __package__ = None
        execfile(sys.argv[0])
    else:
        print (script_help)
