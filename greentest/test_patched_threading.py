import helper

module = helper.prepare_stdlib_test(__file__)

import sys
import subprocess
from subprocess import Popen as _Popen

monkey_patch = 'from gevent import monkey; monkey.patch_all()\n\n'

class MyPopen(_Popen):

    def __init__(self, arg, *args, **kwargs):
        if arg[:2] == [sys.executable, '-c']:
            assert len(arg) == 3, arg
            arg = arg[:2] + [monkey_patch + arg[2]]
        _Popen.__init__(self, arg, *args, **kwargs)

subprocess.Popen = MyPopen

exec module in globals()
