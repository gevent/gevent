import sys
from multiprocessing import spawn, util

__implements__ = ["get_command_line"]
__target__ = "multiprocessing.spawn"


def get_command_line(**kwds):
    '''
    Returns prefix of command line used for spawning a child process
    '''
    if getattr(sys, 'frozen', False):
        return ([sys.executable, '--multiprocessing-fork'] +
                ['%s=%r' % item for item in kwds.items()])
    else:
        prog = 'from gevent import monkey; monkey.patch_all(); ' + \
               'from multiprocessing.spawn import spawn_main; ' + \
               'spawn_main(%s);'
               # 'from trace import Trace; Trace(count=0).runfunc(spawn_main, %s); '

        prog %= ', '.join('%s=%r' % item for item in kwds.items())
        opts = util._args_from_interpreter_flags()
        return [spawn._python_exe] + opts + ['-c', prog, '--multiprocessing-fork']
