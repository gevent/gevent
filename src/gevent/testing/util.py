from __future__ import print_function, absolute_import, division
import re
import sys
import os
import traceback
import unittest
import threading
import subprocess
import time

from . import six
from gevent._config import validate_bool

# pylint: disable=broad-except,attribute-defined-outside-init

runtimelog = []
MIN_RUNTIME = 1.0
BUFFER_OUTPUT = False
# This is set by the testrunner, defaulting to true (be quiet)
# But if we're run standalone, default to false
QUIET = validate_bool(os.environ.get('GEVENTTEST_QUIET', '0'))


class Popen(subprocess.Popen):

    def __enter__(self):
        return self

    def __exit__(self, *args):
        kill(self)


# Coloring code based on zope.testrunner

# These colors are carefully chosen to have enough contrast
# on terminals with both black and white background.
_colorscheme = {
    'normal': 'normal',
    'default': 'default',

    'actual-output': 'red',
    'character-diffs': 'magenta',
    'debug': 'cyan',
    'diff-chunk': 'magenta',
    'error': 'brightred',
    'error-number': 'brightred',
    'exception': 'red',
    'expected-output': 'green',
    'failed-example': 'cyan',
    'filename': 'lightblue',
    'info': 'normal',
    'lineno': 'lightred',
    'number': 'green',
    'ok-number': 'green',
    'skipped': 'brightyellow',
    'slow-test': 'brightmagenta',
    'suboptimal-behaviour': 'magenta',
    'testname': 'lightcyan',
    'warning': 'cyan',
}

_prefixes = [
    ('dark', '0;'),
    ('light', '1;'),
    ('bright', '1;'),
    ('bold', '1;'),
]

_colorcodes = {
    'default': 0,
    'normal': 0,
    'black': 30,
    'red': 31,
    'green': 32,
    'brown': 33, 'yellow': 33,
    'blue': 34,
    'magenta': 35,
    'cyan': 36,
    'grey': 37, 'gray': 37, 'white': 37
}

def _color_code(color):
    prefix_code = ''
    for prefix, code in _prefixes:
        if color.startswith(prefix):
            color = color[len(prefix):]
            prefix_code = code
            break
    color_code = _colorcodes[color]
    return '\033[%s%sm' % (prefix_code, color_code)

def _color(what):
    return _color_code(_colorscheme[what])

def _colorize(what, message, normal='normal'):
    return _color(what) + message + _color(normal)

def log(message, *args, **kwargs):
    """
    Log a *message*

    :keyword str color: One of the values from _colorscheme
    """
    color = kwargs.pop('color', 'normal')
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
            string = _colorize('exception', string)
            sys.stderr.write(string)
        except Exception:
            traceback.print_exc()
    else:
        string = _colorize(color, string)
        sys.stderr.write(string + '\n')

def debug(message, *args, **kwargs):
    """
    Log the *message* only if we're not in quiet mode.
    """
    if not QUIET:
        kwargs.setdefault('color', 'debug')
        log(message, *args, **kwargs)

def killpg(pid):
    if not hasattr(os, 'killpg'):
        return
    try:
        return os.killpg(pid, 9)
    except OSError as ex:
        if ex.errno != 3:
            log('killpg(%r, 9) failed: %s: %s', pid, type(ex).__name__, ex)
    except Exception as ex:
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
        except OSError as ex:
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
    if popen.timer is not None:
        popen.timer.cancel()
    if popen.poll() is not None:
        return
    popen.was_killed = True
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

# A set of environment keys we ignore for printing purposes
IGNORED_GEVENT_ENV_KEYS = {
    'GEVENTTEST_QUIET',
    'GEVENT_DEBUG',
}

# A set of (name, value) pairs we ignore for printing purposes.
# These should match the defaults.
IGNORED_GEVENT_ENV_ITEMS = {
    ('GEVENT_RESOLVER', 'thread'),
    ('GEVENT_RESOLVER_NAMESERVERS', '8.8.8.8')
}

def getname(command, env=None, setenv=None):
    result = []

    env = (env or os.environ).copy()
    env.update(setenv or {})

    for key, value in sorted(env.items()):
        if not key.startswith('GEVENT'):
            continue
        if key in IGNORED_GEVENT_ENV_KEYS:
            continue
        if (key, value) in IGNORED_GEVENT_ENV_ITEMS:
            continue
        result.append('%s=%s' % (key, value))

    if isinstance(command, six.string_types):
        result.append(command)
    else:
        result.extend(command)

    return ' '.join(result)


def start(command, quiet=False, **kwargs):
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

    if not quiet:
        log('+ %s', name)
    popen = Popen(command, preexec_fn=preexec_fn, env=env, **kwargs)
    popen.name = name
    popen.setpgrp_enabled = preexec_fn is not None
    popen.was_killed = False
    popen.timer = None
    if timeout is not None:
        t = threading.Timer(timeout, kill, args=(popen, ))
        t.setDaemon(True)
        t.start()
        popen.timer = t
    return popen


class RunResult(object):
    """
    The results of running an external command.

    If the command was successful, this has a boolean
    value of True; otherwise, a boolean value of false.

    The integer value of this object is the command's exit code.

    """

    def __init__(self,
                 command,
                 run_kwargs,
                 code,
                 output=None, name=None,
                 run_count=0, skipped_count=0):
        self.command = command
        self.run_kwargs = run_kwargs
        self.code = code
        self.output = output
        self.name = name
        self.run_count = run_count
        self.skipped_count = skipped_count


    def __bool__(self):
        return not bool(self.code)

    __nonzero__ = __bool__

    def __int__(self):
        return self.code


def _should_show_warning_output(out):
    if 'Warning' in out:
        # Strip out some patterns we specifically do not
        # care about.
        # from test.support for monkey-patched tests
        out = out.replace('Warning -- reap_children', 'NADA')
        out = out.replace("Warning -- threading_cleanup", 'NADA')

        # The below *could* be done with sophisticated enough warning
        # filters passed to the children

        # collections.abc is the new home; setuptools uses the old one,
        # as does dnspython
        out = out.replace("DeprecationWarning: Using or importing the ABCs", 'NADA')
        # libuv poor timer resolution
        out = out.replace('UserWarning: libuv only supports', 'NADA')
        # Packages on Python 2
        out = out.replace('ImportWarning: Not importing directory', 'NADA')
    return 'Warning' in out

output_lock = threading.Lock()

def _find_test_status(took, out):
    status = '[took %.1fs%s]'
    skipped = ''
    run_count = 0
    skipped_count = 0
    if out:
        m = re.search(r"Ran (\d+) tests in", out)
        if m:
            result = out[m.start():m.end()]
            status = status.replace('took', result)
            run_count = int(out[m.start(1):m.end(1)])

        m = re.search(r' \(skipped=(\d+)\)$', out)
        if m:
            skipped = _colorize('skipped', out[m.start():m.end()])
            skipped_count = int(out[m.start(1):m.end(1)])
    status = status % (took, skipped)
    if took > 10:
        status = _colorize('slow-test', status)
    return status, run_count, skipped_count


def run(command, **kwargs): # pylint:disable=too-many-locals
    "Execute *command*, returning a `RunResult`"
    buffer_output = kwargs.pop('buffer_output', BUFFER_OUTPUT)
    quiet = kwargs.pop('quiet', QUIET)
    verbose = not quiet
    nested = kwargs.pop('nested', False)
    if buffer_output:
        assert 'stdout' not in kwargs and 'stderr' not in kwargs, kwargs
        kwargs['stderr'] = subprocess.STDOUT
        kwargs['stdout'] = subprocess.PIPE
    popen = start(command, quiet=nested, **kwargs)
    name = popen.name
    try:
        time_start = time.time()
        out, err = popen.communicate()
        took = time.time() - time_start
        if popen.was_killed or popen.poll() is None:
            result = 'TIMEOUT'
        else:
            result = popen.poll()
    finally:
        kill(popen)
    assert not err
    with output_lock: # pylint:disable=not-context-manager
        failed = bool(result)
        if out:
            out = out.strip()
            out = out if isinstance(out, str) else out.decode('utf-8', 'ignore')
        if out and (failed or verbose or _should_show_warning_output(out)):
            if out:
                out = '  ' + out.replace('\n', '\n  ')
                out = out.rstrip()
                out += '\n'
                log('| %s\n%s', name, out)
        status, run_count, skipped_count = _find_test_status(took, out)
        if result:
            log('! %s [code %s] %s', name, result, status, color='error')
        elif not nested:
            log('- %s %s', name, status)
    if took >= MIN_RUNTIME:
        runtimelog.append((-took, name))
    return RunResult(command, kwargs, result,
                     output=out, name=name, run_count=run_count, skipped_count=skipped_count)


class NoSetupPyFound(Exception):
    "Raised by find_setup_py_above"

def find_setup_py_above(a_file):
    "Return the directory containing setup.py somewhere above *a_file*"
    root = os.path.dirname(os.path.abspath(a_file))
    while not os.path.exists(os.path.join(root, 'setup.py')):
        prev, root = root, os.path.dirname(root)
        if root == prev:
            # Let's avoid infinite loops at root
            raise NoSetupPyFound('could not find my setup.py above %r' % (a_file,))
    return root

def search_for_setup_py(a_file=None, a_module_name=None, a_class=None, climb_cwd=True):
    if a_file is not None:
        try:
            return find_setup_py_above(a_file)
        except NoSetupPyFound:
            pass

    if a_class is not None:
        try:
            return find_setup_py_above(sys.modules[a_class.__module__].__file__)
        except NoSetupPyFound:
            pass

    if a_module_name is not None:
        try:
            return find_setup_py_above(sys.modules[a_module_name].__file__)
        except NoSetupPyFound:
            pass

    if climb_cwd:
        return find_setup_py_above("./dne")

    raise NoSetupPyFound("After checking %r" % (locals(),))


class ExampleMixin(object):
    "Something that uses the examples/ directory"

    def find_setup_py(self):
        "Return the directory containing setup.py"
        return search_for_setup_py(
            a_file=__file__,
            a_class=type(self)
        )

    @property
    def cwd(self):
        try:
            root = self.find_setup_py()
        except NoSetupPyFound as e:
            raise unittest.SkipTest("Unable to locate file/dir to run: %s" % (e,))

        return os.path.join(root, 'examples')

class TestServer(ExampleMixin,
                 unittest.TestCase):
    args = []
    before_delay = 3
    after_delay = 0.5
    popen = None
    server = None # subclasses define this to be the path to the server.py
    start_kwargs = None

    def start(self):
        try:
            kwargs = self.start_kwargs or {}
            return start([sys.executable, '-u', self.server] + self.args, cwd=self.cwd, **kwargs)
        except NoSetupPyFound as e:
            raise unittest.SkipTest("Unable to locate file/dir to run: %s" % (e,))

    def running_server(self):
        from contextlib import contextmanager

        @contextmanager
        def running_server():
            with self.start() as popen:
                self.popen = popen
                self.before()
                yield
                self.after()
        return running_server()

    def test(self):
        with self.running_server():
            self._run_all_tests()

    def before(self):
        if self.before_delay is not None:
            time.sleep(self.before_delay)
        assert self.popen.poll() is None, '%s died with code %s' % (self.server, self.popen.poll(), )

    def after(self):
        if self.after_delay is not None:
            time.sleep(self.after_delay)
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
