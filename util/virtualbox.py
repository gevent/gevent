import sys
import os
import re
import time
import datetime
from functools import wraps
from subprocess import Popen


def remote_wrapper(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        print '%s: STARTED.' % datetime.datetime.now()
        result = function(*args, **kwargs)
        print '%s: DONE.' % datetime.datetime.now()
        return result
    return wrapper


def get_output(command):
    # XXX use Popen
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


def get_machines(filter_inaccessible=True):
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

    if filter_inaccessible:
        results = [m for m in results if m.get('name') and m.get('name') != '<inaccessible!>']

    return results


def get_machine(name):
    for machine in get_machines():
        if machine['name'] == name:
            return machine


def vbox_get_state(name):
    if not isinstance(name, basestring):
        raise TypeError('Expected string: %r' % (name, ))
    output = get_output('VBoxManage showvminfo %s' % name)
    state = state_re.findall(output)
    assert len(state) == 1, state
    return state[0].split('(')[0].replace(' ', '')


def get_default_machine(desc=None, os='windows'):
    machines = get_machines()

    if os:
        machines = [m for m in machines if os in m.get('os', '').lower()]
        if len(machines) == 1:
            return machines[0]

    if desc:
        machines = [m for m in machines if desc in m.get('desc', '').lower()]
        if len(machines) == 1:
            return machines[0]

    if not machines:
        sys.exit('Could not find an appropriate VirtualBox VM. Pass --machine NAME.')

    if machines:
        sys.exit('More than one machine matches. Pass --machine NAME.')


def system(command, fail=True):
    noisy = system.noisy
    if noisy:
        print 'Running %r' % command
    if isinstance(command, basestring):
        args = command.split()
    else:
        args = command
    result = Popen(args).wait()
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


system.noisy = False


def unlink(path):
    try:
        os.unlink(path)
    except OSError, ex:
        if ex.errno == 2:  # No such file or directory
            return
        raise


class VirtualBox(object):

    def __init__(self, name, username, password='', type=None):
        self.name = name
        self.username = username
        self.password = password
        self.type = type
        self.mkdir_timeout = 15

    def start(self):
        self.initial_state = start(self.name, self.type)
        return self.initial_state

    def stop(self):
        if self.initial_state == 'paused':
            self.pause()
        elif self.initial_state != 'running':
            self.poweroff()

    def pause(self):
        return vbox_pause(self.name)

    def poweroff(self):
        return vbox_poweroff(self.name)

    def restore(self):
        return vbox_restore(self.name)

    def mkdir(self, path, timeout=None):
        if timeout is None:
            timeout = self.mkdir_timeout
        return vbox_mkdir(self.name, path, username=self.username, password=self.password, timeout=timeout)

    def copyto(self, source, dest):
        return vbox_copyto(self.name, source, dest, username=self.username, password=self.password)

    def copyfrom(self, source, dest):
        return vbox_copyfrom(self.name, source, dest, username=self.username, password=self.password)

    def execute(self, exe, arguments):
        return vbox_execute(self.name, exe, arguments, username=self.username, password=self.password)


def start(name, type=None):
    state = vbox_get_state(name)
    if state == 'running':
        pass
    elif state == 'paused':
        vbox_resume(name)
    elif state in ('saved', 'poweredoff'):
        vbox_startvm(name, type)
    else:
        print 'Weird state: %r' % state
        vbox_poweroff(name)
        vbox_startvm(name, type)
    return state


def vbox_startvm(name, type=None):
    if type:
        options = ' --type ' + type
    else:
        options = ''
    system('VBoxManage startvm %s%s' % (name, options))


def vbox_resume(name):
    system('VBoxManage controlvm %s resume' % name)


def vbox_pause(name):
    system('VBoxManage controlvm %s pause' % name)


def vbox_poweroff(name):
    system('VBoxManage controlvm %s poweroff' % name)


def vbox_restorecurrent(name):
    system('VBoxManage snapshot %s restorecurrent' % name)


def vbox_restore(name):
    state = vbox_get_state(name)
    if state == 'saved':
        return
    if state == 'running':
        vbox_poweroff(name)
        time.sleep(0.5)
    vbox_restorecurrent(name)


def _get_options(username=None, password=None, image=None):
    from pipes import quote
    options = ''
    if username:
        options += ' --username %s' % quote(username)
    if password:
        options += ' --password %s' % quote(password)
    if image:
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


def vbox_execute(name, image, arguments=None, username=None, password=None):
    from pipes import quote
    options = _get_options(username, password, image)
    options += ' --wait-stdout --wait-stderr'
    try:
        command = 'VBoxManage guestcontrol %s execute %s' % (name, options)
        if arguments:
            command += ' -- %s' % ' '.join(quote(x) for x in arguments)
        system(command)
    except SystemExit, ex:
        sys.stderr.write(str(ex) + '\n')


if __name__ == '__main__':
    command = sys.argv[1]
    command = globals()['vbox_' + command]
    assert callable(command), command
    command(*sys.argv[2:])
