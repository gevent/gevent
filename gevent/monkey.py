def patch_os():
    from gevent import fork
    import os
    os.fork = fork

def patch_time():
    from gevent import sleep
    _time = __import__('time')
    _time.sleep = sleep

def patch_thread():
    from gevent import thread as green_thread
    thread = __import__('thread')
    thread.get_ident = green_thread.get_ident
    thread.start_new_thread = green_thread.start_new_thread
    thread.LockType = green_thread.LockType
    thread.allocate_lock = green_thread.allocate_lock
    thread.exit = green_thread.exit
    if hasattr(green_thread, 'stack_size'):
        thread.stack_size = green_thread.stack_size

def patch_socket():
    from gevent.socket import GreenSocket, fromfd, wrap_ssl, socketpair
    _socket = __import__('socket')
    _socket.socket = GreenSocket
    _socket.fromfd = fromfd
    _socket.ssl = wrap_ssl
    _socket.socketpair = socketpair
    # also gethostbyname, getaddrinfo

def patch_select():
    from gevent.select import select
    _select = __import__('select')
    globals()['_select_select'] = _select.select
    _select.select = select

def patch_all(socket=True, time=True, select=True, thread=True, os=True):
    # order is important
    if os:
        patch_os()
    if time:
        patch_time()
    if thread:
        patch_thread()
    if socket:
        patch_socket()
    if select:
        patch_select()

# XXX patch unittest to count switches and detect event_count and run the standard tests                    2 hour
# make makefile() return GreenFile. since it uses socket's buffer, while _fileobject creates a new one      2 hour
# probably make GreenSocket be also a file and makefile() just increases refcount and returns self

if __name__=='__main__':
    import sys
    modules = [x.replace('patch_', '') for x in globals().keys() if x.startswith('patch_') and x!='patch_all']
    script_help = """gevent.monkey - monkey patch the standard modules to use gevent.

USAGE: python -m gevent.monkey [MONKEY OPTIONS] script [SCRIPT OPTIONS]

If no OPTIONS present, monkey patches the all modules it can patch.
You can exclude a module with --no-module, e.g. --no-thread. You can
specify a module to patch with --module, e.g. --socket. In this case
only those mentioned on the command line will be patched.

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
        print 'cwd=%s' % os.getcwd()

    patch_all(**args)
    if argv:
        sys.argv = argv
        __package__ = None
        execfile(sys.argv[0])
    else:
        print script_help

