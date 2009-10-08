# Copyright (c) 2009 Denis Bilenko. See LICENSE for details.

import sys

noisy = True

def patch_os():
    from gevent.hub import fork
    import os
    os.fork = fork

def patch_time():
    from gevent.hub import sleep
    _time = __import__('time')
    _time.sleep = sleep

def patch_thread():
    from gevent import thread as green_thread
    thread = __import__('thread')
    if thread.exit is not green_thread.exit:
        thread.get_ident = green_thread.get_ident
        thread.start_new_thread = green_thread.start_new_thread
        thread.LockType = green_thread.LockType
        thread.allocate_lock = green_thread.allocate_lock
        thread.exit = green_thread.exit
        if hasattr(green_thread, 'stack_size'):
            thread.stack_size = green_thread.stack_size
        if noisy and 'threading' in sys.modules:
            sys.stderr.write("gevent.monkey's warning: 'threading' is already imported\n\n")
        # built-in thread._local object won't work as greenlet-local
        if '_threading_local' not in sys.modules:
            import _threading_local
            thread._local = _threading_local.local
        elif noisy:
            sys.stderr.write("gevent.monkey's warning: '_threading_local' is already imported\n\n")

def patch_socket(dns=True):
    from gevent.socket import socket, fromfd, wrap_ssl, socketpair
    _socket = __import__('socket')
    _socket.socket = socket
    _socket.fromfd = fromfd
    _socket.ssl = wrap_ssl
    _socket.socketpair = socketpair
    if dns:
        patch_dns()

def patch_dns():
    from gevent.socket import getaddrinfo, getnameinfo, gethostbyname
    _socket = __import__('socket')
    _socket.getaddrinfo = getaddrinfo
    _socket.getnameinfo = getnameinfo
    _socket.gethostbyname = gethostbyname

def patch_ssl():
    if sys.version_info[:2] >= (2, 6):
        from gevent.socket import wrap_ssl
        import ssl
        ssl.wrap_socket = wrap_ssl

def patch_select():
    from gevent.select import select
    _select = __import__('select')
    globals()['_select_select'] = _select.select
    _select.select = select

def patch_all(socket=True, dns=True, time=True, select=True, thread=True, os=True, ssl=True):
    # order is important
    if os:
        patch_os()
    if time:
        patch_time()
    if thread:
        patch_thread()
    if socket:
        patch_socket(dns=dns)
    if select:
        patch_select()
    if ssl:
        patch_ssl()


if __name__=='__main__':
    modules = [x.replace('patch_', '') for x in globals().keys() if x.startswith('patch_') and x!='patch_all']
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
    if verbose:
        import pprint, os
        print 'gevent.monkey.patch_all(%s)' % ', '.join('%s=%s' % item for item in args.items())
        print 'sys.version=%s' % (sys.version.strip().replace('\n', ' '), )
        print 'sys.path=%s' % pprint.pformat(sys.path)
        print 'sys.modules=%s' % pprint.pformat(sorted(sys.modules.keys()))
        print 'cwd=%s' % os.getcwd()

    patch_all(**args)
    if argv:
        sys.argv = argv
        __package__ = None
        execfile(sys.argv[0])
    else:
        print script_help

