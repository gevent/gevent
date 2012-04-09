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

Before doing anything, winvbox.py runs util/make_dist.py to generate the archive that will
be built/tested. In case of "build" and "test" commands, the default is to pass "--fast" to
make_dist.py. In case of "dist", the default is to run make_dist.py without arguments (which
implies --clean).

It is possible to override the default by passing "--revert", "--clean" or "--fast" explicitly.

Other useful options:

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
import re
import time
import datetime
import glob
from functools import wraps

WINVBOX_LOG = 'winvbox.log'


def main():
    import optparse
    import uuid
    parser = optparse.OptionParser()
    parser.add_option('--fast', action='store_true')
    parser.add_option('--revert', action='store_true')
    parser.add_option('--clean', action='store_true')
    parser.add_option('--python', default='27')
    parser.add_option('--machine')
    parser.add_option('--username')
    parser.add_option('--password', default='')
    parser.add_option('--version', default='dev')
    parser.add_option('-v', '--verbose', action='store_true')

    options, args = parser.parse_args()

    system.noisy = options.verbose

    if not args or args[0] not in ['build', 'test', 'dist', 'noop']:
        sys.exit('Expected a command: build|test|dist')

    command = args[0]
    command_args = args[1:]

    if options.username is None:
        import getpass
        options.username = getpass.getuser()

    archive_filename = make_dist(options, command)
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

    machine = VirtualBox(options.machine, options.username, options.password, this_script_remote, python)
    try:
        machine.mkdir(directory)
        machine.directory = directory
        machine.copyto(archive_filename, directory + '/' + os.path.basename(archive_filename))
        machine.copyto(this_script, this_script_remote)

        function = globals().get('command_%s' % command, command_default)
        function(command, command_args, machine, options)
    finally:
        machine.cleanup()


def command_default(command, command_args, machine, options):
    machine.command(command, command_args)


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


@remote_wrapper
def remote_test(args):
    extract_and_build()
    os.chdir('greentest')
    os.environ['PYTHONPATH'] = '.;..'
    system('%s testrunner.py %s' % (sys.executable, ' '.join(args)))


def command_dist(command, command_args, machine, options):
    machine.command(command, command_args)
    local_name = 'dist_%s.tar' % options.unique
    machine.copyfrom(machine.directory + '/dist.tar', local_name)
    if os.path.exists(local_name):
        system('tar -xvf %s' % local_name)
    else:
        sys.exit('Failed to receive %s' % local_name)


@remote_wrapper
def remote_dist(args):
    extract_and_build()
    system('%s setup.py bdist_egg bdist_wininst' % sys.executable)

    # bdist_msi fails if version is not strict
    system('%s setup.py bdist_msi' % sys.executable, fail=False)

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


def get_make_dist_option(options, command):
    count = sum(1 if x else 0 for x in [options.fast, options.revert, options.clean])
    if count > 1:
        sys.exit('Only one expected of --fast|--revert|--clean')

    if options.fast:
        return '--fast'
    elif options.revert:
        return '--revert'
    elif options.clean:
        return ''
    else:
        if command == 'dist':
            return ''
        else:
            return '--fast'


def make_dist(options, command):
    make_dist_opt = get_make_dist_option(options, command)
    make_dist_command = '%s util/make_dist.py %s %s' % (sys.executable, make_dist_opt, options.version)
    system(make_dist_command)
    filename = glob.glob('/tmp/gevent-make-dist/*.tar.gz')
    assert len(filename) == 1, filename
    return filename[0]


def get_output(command):
    result = os.popen(command)
    output = result.read()
    exitcode = result.close()
    if exitcode:
        sys.stdout.write(output)
        raise SystemExit('Command %r failed with code %r' % (command, exitcode))
    return output


info_re = ('(^|\n)Name:\s*(?P<name>[^\n]+)'
           '(\nGuest OS:\s*(?P<os>[^\n]+))?'
           '\nUUID:\\s*(?P<id>[^\n]+).*?')


info_re = re.compile(info_re, re.DOTALL)
description_re = re.compile('^Description:(?P<desc>.*?\n.*?\n)', re.M)
state_re = re.compile('^State:\s*(.*?)$', re.M)


def get_machines():
    output = get_output('VBoxManage list -l vms 2> /dev/null')
    results = []
    for m in info_re.finditer(output):
        info = m.groupdict()
        info['start'] = m.end(0)
        if results:
            results[-1]['end'] = m.start(0)
        results.append(info)

    for result in results:
        text = output[result.pop('start', 0):result.pop('end', None)]
        d = description_re.findall(text)
        if d:
            assert len(d) == 1, (result, d)
            result['desc'] = d[0].strip()

    return results


def get_state(name):
    output = get_output('VBoxManage showvminfo %s' % name)
    state = state_re.findall(output)
    assert len(state) == 1, state
    return state[0].strip().split('(')[0].strip()


def get_default_machine():
    return _get_default_machine()['name']


def _get_default_machine():
    machines = [m for m in get_machines() if m.get('name') and m.get('name') != '<inaccessible!>']
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


def unlink(path):
    try:
        os.unlink(path)
    except OSError, ex:
        if ex.errno == 2:  # No such file or directory
            return
        raise

RESTORE, POWEROFF, PAUSE = range(3)


class VirtualBox(object):

    def __init__(self, name, username, password, script_path, python_path):
        self.name = name
        self.username = username
        self.password = password
        self.script_path = script_path
        self.python_path = python_path
        self.final_action = None
        self.mkdir_timeout = 15
        self._start()

    def _start(self):
        state = get_state(self.name)
        if state in ('powered off', 'saved', 'aborted'):
            if state != 'saved':
                self.mkdir_timeout = 90
            vbox_startvm(self.name)
            if state != 'saved':
                time.sleep(5)
            if state == 'saved':
                self.final_action = RESTORE
            else:
                self.final_action = POWEROFF
        elif state == 'paused':
            vbox_resume(self.name)
            self.final_action = PAUSE
        elif state == 'running':
            pass
        else:
            sys.exit('Machine %r has invalid state: %r' % (self.name, state))

    def cleanup(self):
        if self.final_action is PAUSE:
            vbox_pause(self.name)
        elif self.final_action == POWEROFF:
            vbox_poweroff(self.name)
        elif self.final_action == RESTORE:
            vbox_restore(self.name)
        self.final_action = None

    def mkdir(self, path):
        vbox_mkdir(self.name, path, username=self.username, password=self.password, timeout=self.mkdir_timeout)

    def copyto(self, source, dest):
        vbox_copyto(self.name, source, dest, username=self.username, password=self.password)

    def copyfrom(self, source, dest):
        vbox_copyfrom(self.name, source, dest, username=self.username, password=self.password)

    def execute(self, exe, arguments):
        vbox_execute(self.name, exe, arguments, username=self.username, password=self.password)

    def command(self, command, command_args=None):
        args = ['-u', self.script_path, 'REMOTE', command] + (command_args or [])
        self.execute(self.python_path, args)


def vbox_startvm(name):
    system('VBoxManage startvm %s' % name)


def vbox_resume(name):
    system('VBoxManage controlvm %s resume' % name)


def vbox_pause(name):
    system('VBoxManage controlvm %s pause' % name)


def vbox_poweroff(name):
    system('VBoxManage controlvm %s poweroff' % name)


def vbox_restorecurrent(name):
    system('VBoxManage snapshot %s restorecurrent' % name)


def vbox_restore(name):
    vbox_poweroff(name)
    count = 0
    while True:
        count += 1
        time.sleep(0.5)
        try:
            vbox_restorecurrent(name)
            break
        except SystemExit:
            if count > 3:
                raise


def _get_options(username=None, password=None, image=None):
    from pipes import quote
    options = ''
    if username is not None:
        options += ' --username %s' % quote(username)
    if password is not None:
        options += ' --password %s' % quote(password)
    if image is not None:
        options += ' --image %s' % quote(image)
    return options


def _vbox_mkdir(name, path, username=None, password=None):
    from pipes import quote
    system('VBoxManage guestcontrol %s mkdir %s%s' % (name, quote(path), _get_options(username, password)))


def vbox_mkdir(name, path, username=None, password=None, timeout=90):
    end = time.time() + timeout
    while True:
        try:
            return _vbox_mkdir(name, path, username=username, password=password)
        except SystemExit:
            if time.time() > end:
                raise
        time.sleep(5)


def vbox_copyto(name, source, dest, username=None, password=None):
    from pipes import quote
    args = (name, quote(os.path.abspath(source)), quote(dest), _get_options(username, password))
    system('VBoxManage guestcontrol %s copyto %s %s%s' % args)


def vbox_copyfrom(name, source, dest, username=None, password=None):
    from pipes import quote
    args = (name, quote(source), quote(os.path.abspath(dest)), _get_options(username, password))
    system('VBoxManage guestcontrol %s copyfrom %s %s%s' % args)


def vbox_execute(name, image, arguments, username=None, password=None):
    from pipes import quote
    options = _get_options(username, password, image)
    options += ' --wait-stdout --wait-stderr'
    arguments = ' '.join(quote(x) for x in arguments)
    try:
        system('VBoxManage guestcontrol %s execute %s%s -- %s' % (name, image, options, arguments))
    except SystemExit, ex:
        sys.stderr.write(str(ex) + '\n')


if __name__ == '__main__':
    if sys.argv[1:2] == ['REMOTE']:
        command = sys.argv[2]
        args = sys.argv[3:]
        function = globals()['remote_' + command]
        os.chdir(os.path.dirname(__file__))
        function(args)
    else:
        main()
