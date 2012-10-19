#!/usr/bin/python -u
import sys
import os
import optparse


def system(cmd):
    sys.stderr.write('+ %s\n' % cmd)
    if os.system(cmd):
        sys.exit('%r failed' % cmd)
    return 0


parser = optparse.OptionParser()
parser.add_option('--host')
parser.add_option('--username', default='Administrator')
parser.add_option('--source')
options, args = parser.parse_args()

if args[0:1] == ['test']:
    source_name = args[1]
    tar_name = source_name.rsplit('.', 1)[0]
    dir_name = tar_name.rsplit('.', 1)[0]
    system('rm -fr %s %s' % (tar_name, dir_name))
    system('gzip -d %s && tar -xf %s' % (source_name, tar_name))
    os.chdir(dir_name)
    os.environ.setdefault('VS90COMNTOOLS', 'C:\\Program Files (x86)\\Microsoft Visual Studio 10.0\\Common7\Tools\\')
    system('%s setup.py build' % sys.executable)
    os.chdir('greentest')
    os.environ['PYTHONPATH'] = '.;..;../..'
    system('%s testrunner.py --expected ../known_failures.txt' % sys.executable)
elif not args:
    assert options.host
    if not options.source:
        import makedist
        options.source = makedist.makedist()

    options.source_name = os.path.basename(options.source)
    options.script_path = os.path.abspath(__file__)
    options.script_name = os.path.basename(__file__)

    system('scp %(source)s %(script_path)s %(username)s@%(host)s:' % options.__dict__)
    system('ssh %(username)s@%(host)s C:/Python27/python.exe -u %(script_name)s test %(source_name)s'  % options.__dict__) 
else:
    sys.exit('Invalid args: %r' % (args, ))
