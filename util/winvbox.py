#!/usr/bin/python
# Copyright (C) 2012 Denis Bilenko. See LICENSE for details.
"""
A script to build/test/make dist for gevent in a Windows Virtual Box machine.

Build the current working directory:

    winvbox.py build

Build and run testrunner:

    winvbox.py test [-- testrunner options]

Make binary installers:

    winvbox.py dist VERSION

Other useful options:

    --source FILENAME     # release tarball of gevent to use
    --python PYTHONVER    # Python version to use. Defaults to "27".
                            Could also be a path to Python executable.
    --machine MACHINE     # VirtualBox machine to use.
    --username LOGIN      # Account name to use for this machine. Defaults to current user name.
    --password PASSWORD   # Password for the account. Defaults to empty string.

winvbox.py assumes Python is located at "C:/Python<VER>/python.exe".

Instead of using --machine option, you can also add word "gevent" to the machine description in
order to be selected by this script.
"""

import sys
import os
import datetime
import glob
from functools import wraps


def main():
    import optparse
    import uuid
    import virtualbox
    parser = optparse.OptionParser()
    parser.add_option('--source')
    parser.add_option('--fast', action='store_true')
    parser.add_option('--revert', action='store_true')
    parser.add_option('--clean', action='store_true')
    parser.add_option('--python', default='27')
    parser.add_option('--machine')
    parser.add_option('--username')
    parser.add_option('--password', default='')
    parser.add_option('--version', default='dev')
    parser.add_option('-v', '--verbose', action='store_true')
    parser.add_option('--type', default='headless')

    options, args = parser.parse_args()

    system.noisy = options.verbose

    if not args or args[0] not in ['build', 'test', 'dist', 'noop']:
        sys.exit('Expected a command: build|test|dist')

    command = args[0]
    command_args = args[1:]

    if options.username is None:
        import getpass
        options.username = getpass.getuser()

    if not options.source:
        import makedist
        options.source = makedist.makedist('dev', fast=True)
    options.source = os.path.abspath(options.source)

    options.unique = uuid.uuid4().hex
    directory = 'c:/tmpdir.%s' % options.unique

    python = options.python
    if not python.endswith('exe') and '/' not in python:
        python = 'C:/Python%s/python.exe' % python

    if not options.machine:
        options.machine = get_default_machine()

    print 'Using directory %r on machine %r. Python: %s' % (directory, options.machine, python)

    this_script = __file__
    if this_script.lower().endswith('.pyc'):
        this_script = this_script[:-1]
    this_script_remote = '%s/%s' % (directory, os.path.basename(this_script))

    machine = virtualbox.VirtualBox(options.machine, options.username, options.password, type=options.type)
    machine.start()
    try:
        machine.mkdir(directory)
        machine.copyto(options.source, directory + '/' + os.path.basename(options.source))
        machine.copyto(this_script, this_script_remote)

        machine.script_path = this_script_remote
        machine.python_path = python
        machine.directory = directory

        function = globals().get('command_%s' % command, command_default)
        function(command, command_args, machine, options)
    finally:
        machine.stop()


def run_command(machine, command, command_args):
    args = ['-u', machine.script_path, 'REMOTE', command] + (command_args or [])
    machine.execute(machine.python_path, args)


def command_default(command, command_args, machine, options):
    run_command(machine, command, command_args)


def remote_wrapper(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        print '%s: STARTED.' % datetime.datetime.now()
        result = function(*args, **kwargs)
        print '%s: DONE.' % datetime.datetime.now()
        return result
    return wrapper


@remote_wrapper
def remote_noop(args):
    print 'Will not do anything.'


@remote_wrapper
def remote_build(args):
    extract_and_build()


def command_test(command, command_args, machine, options):
    run_command(machine, command, command_args)
    local_filename = 'remote-tmp-testrunner-%s.sqlite3' % machine.name
    machine.copyfrom(machine.directory + '/tmp-testrunner.sqlite3', local_filename)
    system('%s util/runteststat.py %s' % (sys.executable, local_filename))


@remote_wrapper
def remote_test(args):
    extract_and_build()
    os.chdir('greentest')
    os.environ['PYTHONPATH'] = '.;..'
    system('%s testrunner.py %s' % (sys.executable, ' '.join(args)), fail=False)
    system('mv tmp-testrunner.sqlite3 ../../')


def command_dist(command, command_args, machine, options):
    run_command(machine, command, command_args)
    local_name = 'dist_%s.tar' % options.unique
    machine.copyfrom(machine.directory + '/dist.tar', local_name)
    if os.path.exists(local_name):
        system('tar -xvf %s' % local_name)
    else:
        sys.exit('Failed to receive %s' % local_name)


@remote_wrapper
def remote_dist(args):
    extract_and_build()

    success = 0

    if not system('%s setup.py bdist_egg' % sys.executable, fail=False):
        success += 1

    if not system('%s setup.py bdist_wininst' % sys.executable, fail=False):
        success += 1

    # bdist_msi fails if version is not strict
    if not system('%s setup.py bdist_msi' % sys.executable, fail=False):
        success += 1

    if not success:
        sys.exit('bdist_egg bdist_wininst and bdist_msi all failed')

    # must use forward slash here. back slashe causes dist.tar to be placed on c:\
    system('tar -cf ../dist.tar dist')


def extract_and_build():
    import tarfile
    filename = glob.glob('gevent*.tar.gz')
    assert len(filename) == 1, filename
    filename = filename[0]
    directory = filename[:-7]

    print 'Extracting %s to %s' % (filename, os.getcwd())
    tarfile.open(filename).extractall()
    print 'cd into %s' % directory
    os.chdir(directory)
    system('%s setup.py build' % sys.executable)


def get_default_machine():
    return _get_default_machine()['name']


def _get_default_machine():
    import virtualbox
    machines = virtualbox.get_machines()
    if len(machines) == 1:
        return machines[0]

    machines = [m for m in machines if 'windows' in m.get('os', '').lower()]
    if len(machines) == 1:
        return machines[0]

    machines = [m for m in machines if 'gevent' in m.get('desc', '').lower()]
    if len(machines) == 1:
        return machines[0]

    if not machines:
        sys.exit('Could not find an appropriate VirtualBox VM. Pass --machine NAME.')

    if machines:
        sys.exit('More than one machine matches "windows" and has "gevent" in description. Pass --machine NAME.')


def system(command, fail=True):
    noisy = system.noisy
    if noisy:
        print 'Running %r' % command
    result = os.system(command)
    if result:
        msg = 'Command %r failed with code %r' % (command, result)
        if fail:
            sys.exit(msg)
        elif noisy:
            sys.stderr.write(msg + '\n')
            return result
    if noisy:
        msg = 'Command %r succeeded' % command
        print msg
        print '-' * min(78, len(msg))
    return result

system.noisy = True


if __name__ == '__main__':
    if sys.argv[1:2] == ['REMOTE']:
        command = sys.argv[2]
        args = sys.argv[3:]
        function = globals()['remote_' + command]
        os.chdir(os.path.dirname(__file__))
        function(args)
    else:
        main()
