#!/usr/bin/env python
"""Unit test runner.

This test runner runs each test module isolated in a subprocess, thus allowing them to
mangle globals freely (i.e. do monkey patching).

To report the results and generate statistics sqlite3 database is used.

Additionally, the subprocess is killed after a timeout has passed. The test case remains
in the database logged with the result 'TIMEOUT'.

The --db option, when provided, specifies sqlite3 database that holds the test results.
By default '/tmp/testresults.sqlite3' is used and is unlinked before used.
"""

# Known issues:
# - screws up warnings location, causing them to appear as originated from testrunner.py

DEFAULT_FILENAME = 'tmp-testrunner.sqlite3'

# the number of seconds each test script is allowed to run
DEFAULT_TIMEOUT = 60

# the number of bytes of output that is recorded; the rest is thrown away
OUTPUT_LIMIT = 50000

import sys
import os
import glob
import re
import traceback
import subprocess
from unittest import _TextTestResult, defaultTestLoader, TextTestRunner
import platform
from datetime import datetime
try:
    from ast import literal_eval
except ImportError:
    literal_eval = eval

try:
    killpg = os.killpg
except AttributeError:
    killpg = None

try:
    import sqlite3
except ImportError:
    sys.stderr.write('Failed to import sqlite3: %s\n' % sys.exc_info()[1])
    sqlite3 = None


base_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB = None
# maps table name to key to value
DEFAULT_PARAMS = {}


def execute(sql, args=None):
    if DB is None:
        return ()
    try:
        if args is None:
            result = DB.execute(sql)
        else:
            result = DB.execute(sql, args)
    except Exception, ex:
        if 'has no column named' not in str(ex):
            log('FAILED query %r %s: %s: %s', sql, args or '', type(ex).__name__, ex)
        raise
    else:
        DB.commit()
        return result


def store_record(table, params):
    d = DEFAULT_PARAMS.get(table, {}).copy()
    d.update(params)
    params = d
    assert params
    keys = sorted(params.keys())
    columns = set()
    for _ in xrange(1000):
        try:
            sql = 'insert or replace into %s (%s) values (%s)' % (table, ', '.join(keys), ', '.join(':%s' % key for key in keys))
            return execute(sql, params).lastrowid
        except sqlite3.OperationalError, ex:
            prefix = 'table ' + table + ' has no column named '
            ex = str(ex)
            if ex.startswith(prefix):
                column = ex[len(prefix):]
                if column and ' ' not in column and column not in columns:
                    execute('alter table %s add column %s' % (table, column))
                    continue
            raise
    raise AssertionError


def delete_record(table, params):
    keys = params.keys()
    sql = 'delete from %s where %s' % (table, ' AND '.join('%s=:%s' % (key, key) for key in keys))
    return execute(sql, params)


class DatabaseTestResult(_TextTestResult):
    separator1 = '=' * 70
    separator2 = '-' * 70

    def startTest(self, test):
        from time import time
        _TextTestResult.startTest(self, test)
        self.params = {'testcase': test.id().replace('__main__.', ''),
                       'result': 'TIMEOUT'}
        testcase_id = store_record('testcase', self.params)
        self.params['id'] = testcase_id
        self.time = time()

    def addSkip(self, test, reason):
        delete_record('testcase', self.params)
        return super(DatabaseTestResult, self).addSkip(test, reason)

    def _store_result(self, test, result):
        from time import time
        self.params['time'] = time() - self.time
        self.params['result'] = result
        store_record('testcase', self.params)
        del self.params
        #self.params.pop('id', None)

    def addSuccess(self, test):
        _TextTestResult.addSuccess(self, test)
        self._store_result(test, 'PASSED')

    def addError(self, test, err):
        _TextTestResult.addError(self, test, err)
        self._store_result(test, format_exc_info(err))

    def addFailure(self, test, err):
        _TextTestResult.addFailure(self, test, err)
        self._store_result(test, format_exc_info(err))


def format_exc_info(exc_info):
    try:
        return '%s: %s' % (exc_info[0].__name__, exc_info[1])
    except Exception:
        return str(exc_info[1]) or str(exc_info[0]) or 'FAILED'


class DatabaseTestRunner(TextTestRunner):

    def _makeResult(self):
        return DatabaseTestResult(self.stream, self.descriptions, self.verbosity)


def execfile_as_main(path):
    import __builtin__
    oldmain = sys.modules["__main__"]
    main = sys.__class__("__main__")
    main.__file__ = path
    main.__builtins__ = __builtin__
    main.__package__ = None
    try:
        sys.modules["__main__"] = main
        return execfile(path, main.__dict__)
    finally:
        sys.modules["__main__"] = oldmain


def worker_main():
    global DB

    if killpg:
        try:
            os.setpgrp()
        except AttributeError:
            pass

    path = sys.argv[1]
    verbosity = int(os.environ['testrunner_verbosity'])
    test_id = int(os.environ['testrunner_test_id'])
    run_id = os.environ['testrunner_run_id']
    db_name = os.environ.get('testrunner_db')
    if db_name:
        DB = sqlite3.connect(db_name)

    DEFAULT_PARAMS['testcase'] = {'run_id': run_id,
                                  'test_id': test_id}

    class _runner(object):

        def __new__(cls, *args, **kawrgs):
            return DatabaseTestRunner(verbosity=verbosity)

    if DB:
        try:
            from unittest import runner
        except ImportError:
            pass
        else:
            runner.TextTestRunner = _runner
        import unittest
        unittest.TextTestRunner = _runner
        import test_support
        test_support.BasicTestRunner = _runner

    sys.argv = sys.argv[1:]

    if os.path.exists(path):
        execfile_as_main(path)
    else:
        test = defaultTestLoader.loadTestsFromName(path)
        result = _runner().run(test)
        sys.exit(not result.wasSuccessful())


def run_subprocess(args, module_name, test_id, verbosity, timeout, capture=True):
    from threading import Timer

    env = os.environ.copy()
    env['testrunner_test_id'] = str(test_id)

    popen_args = [sys.executable, sys.argv[0], 'WORKER'] + args
    popen_args = [str(x) for x in popen_args]
    if capture:
        popen = subprocess.Popen(popen_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    else:
        popen = subprocess.Popen(popen_args, env=env)

    retcode = []

    def killer():
        retcode.append('TIMEOUT')
        sys.stderr.write('Killing %s (%s) because of timeout\n' % (popen.pid, args))
        kill(popen)
        try:
            popen.stdout.close()
        except EnvironmentError:
            pass

    timeout = Timer(timeout, killer)
    timeout.start()
    output = ''
    output_printed = False
    try:
        if capture:
            while True:
                data = popen.stdout.read(1)
                if not data:
                    break
                output += data
                if verbosity >= 2:
                    sys.stdout.write(data)
                    output_printed = True
        retcode.append(popen.wait())
    finally:
        timeout.cancel()
        kill(popen)

    # QQQ compensating for worker_main' screw up
    output = output.replace(' (__main__.', ' (' + module_name + '.')
    return retcode[0], output, output_printed


def kill(popen):
    if killpg is not None:
        try:
            killpg(popen.pid, 9)
        except OSError, ex:
            if ex.errno != 3:
                log('killpg(%r, 9) failed: %s: %s', popen.pid, type(ex).__name__, ex)
    if sys.platform.startswith('win'):
        ignore_msg = 'ERROR: The process "%s" not found.' % popen.pid
        err = subprocess.Popen('taskkill /F /PID %s /T' % popen.pid, stderr=subprocess.PIPE).communicate()[1]
        if err and err.strip() not in [ignore_msg, '']:
            sys.stderr.write(repr(err))
    try:
        if hasattr(popen, 'kill'):
            popen.kill()
        elif hasattr(os, 'kill'):
            os.kill(popen.pid, 9)
    except EnvironmentError:
        pass


def read_timeout(source):
    data = open(source, 'rb').read(1000)
    matches = re.findall('^# testrunner timeout: (\d+)', data)
    if not matches:
        return
    assert len(matches) == 1, (source, matches)
    return int(matches[0])


def spawn_subprocess(args, options, run_id):
    success = False
    module_name = args[0]
    if module_name.endswith('.py'):
        module_name = module_name[:-3]
    params = {'started_at': datetime.now(),
              'module': module_name,
              'run_id': run_id}
    test_id = store_record('test', params)
    params['test_id'] = test_id

    timeout = options.timeout

    if timeout is None:
        timeout = read_timeout(args[0]) or DEFAULT_TIMEOUT
        if '-dbg' in sys.executable:
            timeout *= 5
        if 'test_patched_' in args[0]:
            timeout *= 2

    retcode, output, output_printed = run_subprocess(args, module_name, test_id, verbosity=options.verbosity, timeout=timeout, capture=options.capture)

    if len(output) > OUTPUT_LIMIT:
        warn = '<AbridgedOutputWarning>'
        output = output[:OUTPUT_LIMIT - len(warn)] + warn
    if retcode:
        if retcode == 1 and 'test_support.TestSkipped' in output:
            pass
        else:
            if not output_printed and options.verbosity >= -1:
                sys.stdout.write(output)
            log('%s failed with code %s', ' '.join(args), retcode)
    elif retcode == 0:
        if not output_printed and options.verbosity >= 1:
            sys.stdout.write(output)
        if options.verbosity >= 0:
            log('%s passed', ' '.join(args))
        success = True
    else:
        log('%s timed out', ' '.join(args))
    sys.stdout.flush()
    params['output'] = output
    params['retcode'] = retcode
    store_record('test', params)
    if not list(execute('select id from testcase where test_id=?', (test_id, ))):
        store_record('testcase', {'module': module_name,
                                  'run_id': run_id,
                                  'test_id': test_id,
                                  'testcase': '',
                                  'result': 'PASSED' if not retcode else 'FAILED'})
    return success


def get_platform_details():
    functions = ['architecture',
                 'machine',
                 'linux_distribution',
                 'dist',
                 'node',
                 'processor',
                 'python_build',
                 'python_compiler',
                 'python_implementation',
                 'python_version',
                 'release',
                 'system',
                 'version',
                 'win32_ver',
                 'mac_ver',
                 'libc_ver']

    result = {}
    for name in functions:
        function = getattr(platform, name, None)
        if function is not None:
            try:
                value = function()
            except Exception:
                traceback.print_exc()
            else:
                if not empty(value):
                    result[name] = str(value)

    dist = result.pop('dist', None)
    result['linux_distribution'] = result.get('linux_distribution', None) or dist

    return result


def empty(container):
    if not container:
        return True
    if not isinstance(container, (list, tuple)):
        return False
    for item in container:
        if not empty(item):
            return False
    return True


def read_output(command, **kwargs):
    p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    out, err = p.communicate()
    if err:
        raise SystemExit(err)
    if p.poll():
        raise SystemExit('%r failed with code %r' % (command, p.poll()))
    output = out.strip()
    if not output:
        raise SystemExit('%r failed' % (command, ))
    return output


def get_backend():
    return read_output([sys.executable, '-c', 'import gevent.core; print gevent.core.loop().backend'])


def get_greenlet_version():
    return read_output([sys.executable, '-c', 'import greenlet; print greenlet.__version__'])


def get_gevent_core_details():
    import gevent.core
    backend = get_backend()
    recommended_backends = ','.join(gevent.core.recommended_backends())
    supported_backends = ','.join(gevent.core.supported_backends())
    assert backend and backend in supported_backends, repr(backend)
    return {'backend': backend,
            'recommended_backends': recommended_backends,
            'supported_backends': supported_backends}


def get_environ_details():
    result = {}
    for key, value in os.environ.items():
        if key.startswith('GEVENT'):
            result[key] = value
    return result


def get_variables(names, limit=10000):
    data = open(os.path.join(base_directory, 'gevent', '__init__.py')).read(limit)
    results = []
    for name in names:
        result = re.search('^' + name + r'\s*=\s*(.+)\s*$', data, re.M)
        if result:
            result = literal_eval(result.group(1))
            results.append(result)
        else:
            results.append(None)
    return results


def get_gevent_version():
    version, changeset = get_variables(['__version__', '__changeset__'])
    assert version
    if changeset:
        version = '%s(%s)' % (version, changeset)
    return version


def testrunner(options, args):
    import uuid
    run_id = str(uuid.uuid4())
    details = {'run_id': run_id,
               'gevent': get_gevent_version(),
               'greenlet': get_greenlet_version(),
               'python_exe': sys.executable,
               'started_at': datetime.now()}

    keys = sorted(details.keys())
    keys.remove('run_id')

    def update(data):
        keys.extend(sorted(data.keys()))
        details.update(data)

    update(get_gevent_core_details())
    update(get_environ_details())
    update(get_platform_details())

    execute('CREATE TABLE IF NOT EXISTS run (run_id PRIMARY_KEY, %s);' % ', '.join(keys))
    execute('CREATE TABLE IF NOT EXISTS test (test_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id);')
    execute('CREATE TABLE IF NOT EXISTS testcase (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id, test_id INTEGER);')

    assert details
    store_record('run', details)
    os.environ['testrunner_run_id'] = str(run_id)

    success = True
    if not args:
        args = glob.glob('test_*.py')
        args.remove('test_support.py')
    real_args = []
    for arg in args:
        if os.path.exists(arg):
            real_args.append([arg])
        else:
            real_args[-1].append(arg)
    for arg in real_args:
        try:
            success = spawn_subprocess(arg, options, run_id) and success
        except Exception:
            traceback.print_exc()
    if not success:
        sys.exit(1)


def main():
    global DB
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', default=0, action='count')
    parser.add_option('-q', '--quiet', default=0, action='count')
    parser.add_option('--verbosity', default=0, type='int', help=optparse.SUPPRESS_HELP)
    parser.add_option('--db')
    parser.add_option('--no-db', dest='db', action='store_false')
    parser.add_option('--no-capture', dest='capture', default=True, action='store_false')
    parser.add_option('--timeout', type=float, metavar='SECONDS')

    options, args = parser.parse_args()
    options.verbosity += options.verbose - options.quiet

    show_results = False

    if sqlite3 is None:
        assert options.db is None, 'Cannot use --db option because sqlite3 is not available'
    else:
        if options.db is None:
            if os.path.exists(DEFAULT_FILENAME):
                os.unlink(DEFAULT_FILENAME)
            db = DEFAULT_FILENAME
            show_results = db
        else:
            db = options.db

        if db:
            db = os.path.abspath(db)
            directory = os.path.dirname(db)
            if not os.path.exists(directory):
                os.makedirs(directory)
            DB = sqlite3.connect(db)
            os.environ['testrunner_db'] = db

    os.environ['testrunner_verbosity'] = str(options.verbosity)

    try:
        testrunner(options, args)
    finally:
        if show_results and os.path.exists(show_results):
            os.system('%s %s %s' % (sys.executable, os.path.join(base_directory, 'util', 'stat.py'), show_results))


def log(message, *args):
    try:
        string = message % args
    except Exception:
        traceback.print_exc()
        try:
            message = '%r %% %r\n\n' % (message, args)
        except Exception:
            pass
        try:
            sys.stderr.write(message)
        except Exception:
            traceback.print_exc()
    else:
        sys.stderr.write(string + '\n')


if __name__ == '__main__':
    if sys.argv[1:2] == ['WORKER']:
        del sys.argv[1]
        worker_main()
    else:
        main()
