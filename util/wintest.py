#!/usr/bin/python -u
"""
Unix utilities must be installed on target machine for this to work: http://unxutils.sourceforge.net/
"""
import sys
import os
import argparse


def system(cmd, exit=True):
    sys.stderr.write('+ %s\n' % cmd)
    retcode = os.system(cmd)
    if retcode:
        if exit:
            sys.exit('%r failed' % cmd)
    return retcode


parser = argparse.ArgumentParser()
parser.add_argument('--host')
parser.add_argument('--username', default='Administrator')
parser.add_argument('--source')
parser.add_argument('--dist', action='store_true')
parser.add_argument('--python', default='27')
parser.add_argument('args', nargs='*')
options = parser.parse_args()
args = options.args


def prepare():
    source_name = args[1]
    tar_name = source_name.rsplit('.', 1)[0]
    dir_name = tar_name.rsplit('.', 1)[0]
    system('rm -fr %s %s' % (tar_name, dir_name))
    system('gzip -d %s && tar -xf %s' % (source_name, tar_name))
    os.chdir(dir_name)
    os.environ.setdefault('VS90COMNTOOLS', 'C:\\Program Files\\Microsoft Visual Studio 10.0\\Common7\Tools\\')

if args[0:1] == ['test']:
    prepare()
    system('%s setup.py build' % sys.executable)
    os.chdir('greentest')
    os.environ['PYTHONPATH'] = '.;..;../..'
    system('%s testrunner.py --config ../known_failures.py' % sys.executable)
elif args[0:1] == ['dist']:
    prepare()
    success = 0
    for command in ['bdist_egg', 'bdist_wininst', 'bdist_msi']:
        cmd = sys.executable + ' setup.py ' + command
        if not system(cmd, exit=False):
            success += 1
    if not success:
        sys.exit('bdist_egg bdist_wininst and bdist_msi all failed')
elif not args:
    assert options.host
    if not options.source:
        import makedist
        options.source = makedist.makedist()

    options.source_name = os.path.basename(options.source)
    options.script_path = os.path.abspath(__file__)
    options.script_name = os.path.basename(__file__)

    if options.python.isdigit():
        options.python = 'C:/Python' + options.python + '/python.exe'

    tar_name = options.source_name.rsplit('.', 1)[0]
    dir_name = tar_name.rsplit('.', 1)[0]
    options.dir_name = dir_name

    system('scp %(source)s %(script_path)s %(username)s@%(host)s:' % options.__dict__)
    if options.dist:
        system('ssh %(username)s@%(host)s %(python)s -u %(script_name)s dist %(source_name)s' % options.__dict__)
        try:
            os.mkdir('dist')
        except OSError:
            pass
        system('scp -r %(username)s@%(host)s:%(dir_name)s/dist/ dist' % options.__dict__)
    else:
        system('ssh %(username)s@%(host)s C:/Python27/python.exe -u %(script_name)s test %(source_name)s' % options.__dict__)
else:
    sys.exit('Invalid args: %r' % (args, ))
