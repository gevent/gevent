from __future__ import with_statement
import sys
import os
import re
import traceback
import unittest
import threading
import time
from datetime import timedelta
from gevent import subprocess, sleep, spawn_later


SLEEP = 0.1
runtimelog = []
MIN_RUNTIME = 1.0
BUFFER_OUTPUT = False


class Popen(subprocess.Popen):

    def __enter__(self):
        return self

    def __exit__(self, *args):
        kill(self)


def log(message, *args):
    try:
        if args:
            string = message % args
        else:
            string = message
    except Exception:
        traceback.print_exc()
        try:
            string = '%r %% %r\n\n' % (message, args)
        except Exception:
            pass
        try:
            sys.stderr.write(string)
        except Exception:
            traceback.print_exc()
    else:
        sys.stderr.write(string + '\n')


def killpg(pid):
    if not hasattr(os, 'killpg'):
        return
    try:
        return os.killpg(pid, 9)
    except OSError, ex:
        if ex.errno != 3:
            log('killpg(%r, 9) failed: %s: %s', pid, type(ex).__name__, ex)
    except Exception, ex:
        log('killpg(%r, 9) failed: %s: %s', pid, type(ex).__name__, ex)


def kill_processtree(pid):
    ignore_msg = 'ERROR: The process "%s" not found.' % pid
    err = subprocess.Popen('taskkill /F /PID %s /T' % pid, stderr=subprocess.PIPE).communicate()[1]
    if err and err.strip() not in [ignore_msg, '']:
        log('%r', err)


def _kill(popen):
    if hasattr(popen, 'kill'):
        try:
            popen.kill()
        except OSError, ex:
            if ex.errno == 3:  # No such process
                return
            if ex.errno == 13:  # Permission denied (translated from windows error 5: "Access is denied")
                return
            raise
    else:
        try:
            os.kill(popen.pid, 9)
        except EnvironmentError:
            pass


def kill(popen):
    try:
        if getattr(popen, 'setpgrp_enabled', None):
            killpg(popen.pid)
        elif sys.platform.startswith('win'):
            kill_processtree(popen.pid)
    except Exception:
        traceback.print_exc()
    try:
        _kill(popen)
    except Exception:
        traceback.print_exc()
    try:
        popen.wait()
    except Exception:
        traceback.print_exc()


def getname(command, env=None, setenv=None):
    result = []

    env = (env or os.environ).copy()
    env.update(setenv or {})

    for key, value in sorted(env.items()):
        if key.startswith('GEVENT_') or key.startswith('GEVENTARES_'):
            result.append('%s=%s' % (key, value))

    if isinstance(command, basestring):
        result.append(command)
    else:
        result.extend(command)

    return ' '.join(result)


def start(command, **kwargs):
    timeout = kwargs.pop('timeout', None)
    preexec_fn = None
    if not os.environ.get('DO_NOT_SETPGRP'):
        preexec_fn = getattr(os, 'setpgrp', None)
    env = kwargs.pop('env', None)
    setenv = kwargs.pop('setenv', None) or {}
    name = getname(command, env=env, setenv=setenv)
    if preexec_fn is not None:
        setenv['DO_NOT_SETPGRP'] = '1'
    if setenv:
        if env:
            env = env.copy()
        else:
            env = os.environ.copy()
        env.update(setenv)

    log('+ %s', name)
    popen = Popen(command, preexec_fn=preexec_fn, env=env, **kwargs)
    popen.name = name
    popen.setpgrp_enabled = preexec_fn is not None
    if timeout is not None:
        popen._killer = spawn_later(timeout, kill, popen)
        popen._killer._start_event.ref = False   # XXX add 'ref' property to greenlet
    else:
        popen._killer = None
    return popen


class RunResult(object):

    def __init__(self, code, output=None, name=None):
        self.code = code
        self.output = output
        self.name = name

    def __nonzero__(self):
        return bool(self.code)

    def __int__(self):
        return self.code


def run(command, **kwargs):
    buffer_output = kwargs.pop('buffer_output', BUFFER_OUTPUT)
    if buffer_output:
        assert 'stdout' not in kwargs and 'stderr' not in kwargs, kwargs
        kwargs['stderr'] = subprocess.STDOUT
        kwargs['stdout'] = subprocess.PIPE
    popen = start(command, **kwargs)
    name = popen.name
    try:
        time_start = time.time()
        out, err = popen.communicate()
        took = time.time() - time_start
        if popen.poll() is None:
            result = 'TIMEOUT'
        else:
            result = popen.poll()
    finally:
        if popen._killer is not None:
            popen._killer.kill(block=False)
        kill(popen)
    assert not err
    if out:
        out = out.strip()
        if out:
            out = '  ' + out.replace('\n', '\n  ')
            out = out.rstrip()
            out += '\n'
            log('| %s\n%s', name, out)
    if result:
        log('! %s [code %s] [took %.1fs]', name, result, took)
    else:
        log('- %s [took %.1fs]', name, took)
    if took >= MIN_RUNTIME:
        runtimelog.append((-took, name))
    return RunResult(result, out, name)


def parse_command(parts):
    if isinstance(parts, basestring):
        parts = parts.split()
    environ = []
    if parts[0] == '-':
        del parts[0]
    elif parts[0] == '*':
        del parts[0]
        environ = None
    elif '=' in parts[0]:
        while parts[0].count('='):
            environ.append(parts[0])
            del parts[0]
    exe = parts[0]
    del parts[0]
    if exe == '*':
        exe = None
    else:
        assert exe
        assert not exe.startswith('-'), repr(exe)
    return environ, exe, parts


def parse_line(line):
    """
    >>> parse_line("* - /usr/bin/python -u test.py")
    (None, [], '/usr/bin/python', ['-u', 'test.py'])

    >>> parse_line("win32 * C:\\Python27\\python.exe -u -m monkey_test --Event test_subprocess.py")
    ('win32', None, 'C:\\\\Python27\\\\python.exe', ['-u', '-m', 'monkey_test', '--Event', 'test_subprocess.py'])

    >>> parse_line("* GEVENTARES_SERVERS=8.8.8.8 GEVENT_RESOLVER=ares * -u test__socket_dns.py")
    (None, ['GEVENTARES_SERVERS=8.8.8.8', 'GEVENT_RESOLVER=ares'], None, ['-u', 'test__socket_dns.py'])
    """
    parts = line.split()
    if len(parts) < 4:
        raise ValueError('Expected "platform environ executable arguments", got %r' % line)
    platform = parts[0]
    if platform == '*':
        platform = None
    return (platform, ) + parse_command(parts[1:])


def match_word(pattern, word):
    if isinstance(pattern, str) and isinstance(word, str) and '(' in pattern or '*' in pattern or '?' in pattern or '[' in pattern:
        return re.match(pattern, word)
    return pattern == word


def match_environ(expected_environ, actual_environ):
    """
    >>> match_environ('GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8',
    ...               'GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 GEVENT_FILE=thread')
    True
    >>> match_environ('GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.7',
    ...               'GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 GEVENT_FILE=thread')
    False
    >>> match_environ('GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 GEVENT_FILE=',
    ...               'GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 GEVENT_FILE=thread')
    False
    """
    if expected_environ is None:
        return True
    if isinstance(expected_environ, basestring):
        expected_environ = expected_environ.split()
    if isinstance(actual_environ, basestring):
        actual_environ = actual_environ.split()
    expected_environ = dict(x.split('=') for x in expected_environ)
    actual_environ = dict(x.split('=') for x in actual_environ)
    for key, expected_value in expected_environ.items():
        value = actual_environ.pop(key, None)
        if value is not None and value != expected_value:
            return False
    return True


def match_line(line, command):
    expected_platform, expected_environ, expected_exe, expected_arguments = parse_line(line)
    if expected_platform is not None and expected_platform != sys.platform:
        return
    environ, exe, arguments = parse_command(command)
    if not match_environ(expected_environ, environ):
        return
    if expected_exe is not None and not match_word(expected_exe, exe):
        return
    return expected_arguments == arguments


def matches(expected, command):
    """
    >>> matches(["* * C:\Python27\python.exe -u -m monkey_test --Event test_threading.py"], "C:\Python27\python.exe -u -m monkey_test --Event test_threading.py")
    True
    >>> matches(['* * /usr/bin/python2.5(-dbg)? -u -m monkey_test --Event test_urllib2net.py'], "/usr/bin/python2.5-dbg -u -m monkey_test --Event test_urllib2net.py")
    True
    >>> matches(['* * /usr/bin/python2.5(-dbg)? -u -m monkey_test --Event test_urllib2net.py'], "/usr/bin/python2.5 -u -m monkey_test --Event test_urllib2net.py")
    True
    >>> matches(['* * /usr/bin/python2.5(-dbg)? -u -m monkey_test --Event test_urllib2net.py'], "/usr/bin/python2.6 -u -m monkey_test --Event test_urllib2net.py")
    False
    >>> matches(['* GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 python -u test__subprocess.py'],
    ...          "GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 GEVENT_FILE=thread python -u test__subprocess.py")
    True
    """
    for line in expected:
        if match_line(line, command):
            return True
    return False


def format_seconds(seconds):
    if seconds < 20:
        return '%.1fs' % seconds
    seconds = str(timedelta(seconds=round(seconds)))
    if seconds.startswith('0:'):
        seconds = seconds[2:]
    return seconds


def report(total, failed, exit=True, took=None, expected=None):
    if runtimelog:
        log('\nLongest-running tests:')
        runtimelog.sort()
        length = len('%.1f' % -runtimelog[0][0])
        frmt = '%' + str(length) + '.1f seconds: %s'
        for delta, name in runtimelog[:5]:
            log(frmt, -delta, name)
    if took:
        took = ' in %s' % format_seconds(took)
    else:
        took = ''

    failed_expected = []
    failed_unexpected = []

    if failed:
        log('\n%s/%s tests failed%s', len(failed), total, took)
        expected = set(expected or [])
        for name in failed:
            if matches(expected, name):
                failed_expected.append(name)
            else:
                failed_unexpected.append(name)

        if failed_expected:
            log('\n%s/%s expected failures', len(failed_expected), total)
            for name in failed_expected:
                log(' - %s', name)

        if failed_unexpected:
            log('\n%s/%s unexpected failures', len(failed_unexpected), total)
            for name in failed_unexpected:
                log(' - %s', name)
    else:
        log('\n%s tests passed%s', total, took)
    if exit:
        if failed_unexpected:
            sys.exit(min(100, len(failed_unexpected)))
        if total <= 0:
            sys.exit('No tests found.')


class TestServer(unittest.TestCase):
    cwd = '../examples/'
    args = []
    before_delay = 1
    after_delay = 0.5

    def test(self):
        with start([sys.executable, '-u', self.server] + self.args, cwd=self.cwd) as popen:
            self.popen = popen
            self.before()
            self._run_all_tests()
            self.after()

    def before(self):
        if self.before_delay is not None:
            sleep(self.before_delay)
        assert self.popen.poll() is None, '%s died with code %s' % (self.server, self.popen.poll(), )

    def after(self):
        if self.after_delay is not None:
            sleep(self.after_delay)
            assert self.popen.poll() is None, '%s died with code %s' % (self.server, self.popen.poll(), )

    def _run_all_tests(self):
        ran = False
        for method in sorted(dir(self)):
            if method.startswith('_test'):
                function = getattr(self, method)
                if callable(function):
                    function()
                    ran = True
        assert ran


class alarm(threading.Thread):
    # can't use signal.alarm because of Windows

    def __init__(self, timeout):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.timeout = timeout
        self.start()

    def run(self):
        time.sleep(self.timeout)
        sys.stderr.write('Timeout.\n')
        os._exit(5)
