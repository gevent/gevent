import os
import glob

for filename in glob.glob('test_patched_*.py'):
    cmd = 'cp patched_test.py %s' % filename
    print cmd
    os.system(cmd)
