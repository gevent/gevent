import os
import glob
import helper
before = set(glob.glob('@test_*_tmp'))
helper.run(__file__, globals())
for filename in set(glob.glob('@test_*_tmp')) - before:
    os.unlink(filename)
import subprocess
assert 'gevent' in repr(subprocess.Popen.__init__.im_func.func_code), repr(subprocess.Popen.__init__.im_func.func_code)
