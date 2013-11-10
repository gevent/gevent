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


parser = argparse.ArgumentParser(prog='gevent')
parser.add_argument('--host', dest='host')
parser.add_argument('--username', default='Administrator', dest='username')
parser.add_argument('--source', dest='source_name', dest='source')
parser.add_argument('--dist', action='store_true', dest='dist')
parser.add_argument('--python', default='27', dest='python_version')
args = parser.parse_args()


def prepare():
    tar_name = source_name.rsplit('.', 1)[0]
    dir_name = tar_name.rsplit('.', 1)[0]
    system('rm -fr %s %s' % (tar_name, dir_name))
    system('gzip -d %s && tar -xf %s' % (source_name, tar_name))
    os.chdir(dir_name)
    os.environ.setdefault('VS90COMNTOOLS', 'C:\\Program Files\\Microsoft Visual Studio 10.0\\Common7\Tools\\')

if dist == 'test':
    prepare()
    system('%s setup.py build' % sys.executable)
    os.chdir('greentest')
    os.environ['PYTHONPATH'] = '.;..;../..'
    system('%s testrunner.py --expected ../known_failures.txt' % sys.executable)
elif dist == 'dist':
    prepare()
    success = 0
    for command in ['bdist_egg', 'bdist_wininst', 'bdist_msi']:
        cmd = sys.executable + ' setup.py ' + command
        if not system(cmd, exit=False):
            success += 1
    if not success:
        sys.exit('bdist_egg bdist_wininst and bdist_msi all failed')
elif not args:
    assert host
    if not source:
        import makedist
        source = makedist.makedist()

    source_name = os.path.basename(options.source)
    script_path = os.path.abspath(__file__)
    script_name = os.path.basename(__file__)

    if python_version.isdigit():
        options.python = 'C:/Python' + python_version + '/python.exe'

    tar_name = options.source_name.rsplit('.', 1)[0]
    dir_name = tar_name.rsplit('.', 1)[0]

    system('scp %(source)s %(script_path)s %(username)s@%(host)s:' % source_name, source_path, username, host)
    if dist:
        system('ssh %(username)s@%(host)s %(python)s -u %(script_name)s dist %(source_name)s'  % username, host, python_version, source_name)
        try:
            os.mkdir('dist')
        except OSError:
            pass
        system('scp -r %(username)s@%(host)s:%(dir_name)s/dist/ dist' % username, host, dir_name)
    else:
        system('ssh %(username)s@%(host)s C:/Python27/python.exe -u %(script_name)s test %(source_name)s'  % username, host, script_name, source_name)
else:
    sys.exit('Invalid args: %r' % (args, ))
