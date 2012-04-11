#!/usr/bin/python
"""Unit test runner.

This test runner runs each test module isolated in a subprocess, thus allowing them to
mangle globals freely (i.e. do monkey patching).

To report the results and generate statistics sqlite3 database is used.

Additionally, the subprocess is killed after a timeout has passed. The test case remains
in the database logged with the result 'TIMEOUT'.

The --db option, when provided, specifies sqlite3 database that holds the test results.
By default 'testresults.sqlite3' is used in the current directory.

The results are stored in the following 2 tables:

testcase:

  runid   | test   | testcase        | result                 | time |
  --------+--------+-----------------+------------------------+------+
  abc123  | module | class.function  | PASSED|FAILED|TIMEOUT  | 0.01 |

test:

  runid   | test    | python | output | retcode | changeset   | uname | started_at |
  --------+---------+--------+--------+---------+-------------+-------+------------+
  abc123  | module  | 2.6.4  | ...    |       1 | 123_fe43ca+ | Linux |            |

Set runid with --runid option. It must not exists in the database. The random
one will be selected if not provided.
"""

# Known issues:
# - screws up warnings location, causing them to appear as originated from testrunner.py

# the number of seconds each test script is allowed to run
DEFAULT_TIMEOUT = 120

# the number of bytes of output that is recorded; the rest is thrown away
OUTPUT_LIMIT = 50000

ignore_tracebacks = ['ExpectedException', 'test_support.TestSkipped', 'test.test_support.TestSkipped']

import sys
import os
import glob
import re
import traceback
from unittest import _TextTestResult, defaultTestLoader, TextTestRunner
import platform

try:
    import sqlite3
except ImportError, ex:
    sys.stderr.write('Failed to import sqlite3: %s\n' % ex)
    try:
        import pysqlite2.dbapi2 as sqlite3
    except ImportError, ex:
        sys.stderr.write('Failed to import pysqlite2.dbapi2: %s\n' % ex)
        sqlite3 = None

_column_types = {'time': 'real'}


def store_record(database_path, table, dictionary, _added_colums_per_db={}):
    if sqlite3 is None:
        return
    conn = sqlite3.connect(database_path)
    _added_columns = _added_colums_per_db.setdefault(database_path, set())
    keys = dictionary.keys()
    for key in keys:
        if key not in _added_columns:
            try:
                sql = '''alter table %s add column %s %s''' % (table, key, _column_types.get(key))
                conn.execute(sql)
                conn.commit()
                _added_columns.add(key)
            except sqlite3.OperationalError, ex:
                if 'duplicate column' not in str(ex).lower():
                    raise
    sql = 'insert or replace into %s (%s) values (%s)' % (table, ', '.join(keys), ', '.join(':%s' % key for key in keys))
    cursor = conn.cursor()
    try:
        cursor.execute(sql, dictionary)
    except sqlite3.Error:
        print 'sql=%r\ndictionary=%r' % (sql, dictionary)
        raise
    conn.commit()
    return cursor.lastrowid


class DatabaseTestResult(_TextTestResult):
    separator1 = '=' * 70
    separator2 = '-' * 70

    def __init__(self, database_path, runid, module_name, stream, descriptions, verbosity):
        _TextTestResult.__init__(self, stream, descriptions, verbosity)
        self.database_path = database_path
        self.params = {'runid': runid,
                       'test': module_name}

    def startTest(self, test):
        _TextTestResult.startTest(self, test)
        self.params['testcase'] = test.id().replace('__main__.', '')
        self.params['result'] = 'TIMEOUT'
        row_id = store_record(self.database_path, 'testcase', self.params)
        self.params['id'] = row_id
        from time import time
        self.time = time()

    def _store_result(self, test, result):
        self.params['result'] = result
        from time import time
        self.params['time'] = time() - self.time
        store_record(self.database_path, 'testcase', self.params)
        self.params.pop('id', None)

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

    def __init__(self, database_path, runid, module_name, stream=sys.stderr, descriptions=1, verbosity=1):
        self.database_path = database_path
        self.runid = runid
        self.module_name = module_name
        TextTestRunner.__init__(self, stream=stream, descriptions=descriptions, verbosity=verbosity)

    def _makeResult(self):
        return DatabaseTestResult(self.database_path, self.runid, self.module_name, self.stream, self.descriptions, self.verbosity)


def get_changeset():
    try:
        diff = os.popen(r"hg diff 2> /dev/null").read().strip()
    except Exception:
        diff = None
    try:
        changeset = os.popen(r"hg log -r tip 2> /dev/null | grep changeset").readlines()[0]
        changeset = changeset.replace('changeset:', '').strip().replace(':', '_')
        if diff:
            changeset += '+'
    except Exception:
        changeset = ''
    return changeset


def get_libevent_version():
    from gevent import core
    libevent_version = core.get_version()
    if core.get_header_version() != core.get_version() and core.get_header_version() is not None:
        libevent_version += '/headers=%s' % core.get_header_version()
    return libevent_version


def get_tempnam():
    import warnings
    warnings.filterwarnings('ignore', 'tempnam is a potential security risk to your program')
    try:
        tempnam = os.tempnam()
    finally:
        del warnings.filters[0]
    return os.path.join(os.path.dirname(tempnam), 'testresults.sqlite3')


def run_tests(options, args):
    arg = args[0]
    module_name = arg
    if module_name.endswith('.py'):
        module_name = module_name[:-3]

    class _runner(object):

        def __new__(cls, *args, **kawrgs):
            return DatabaseTestRunner(database_path=options.db, runid=options.runid, module_name=module_name, verbosity=options.verbosity)

    if options.db:
        import unittest
        unittest.TextTestRunner = _runner
        import test_support
        test_support.BasicTestRunner = _runner

    sys.argv = args
    globals()['__file__'] = arg

    if os.path.exists(arg):
        execfile(arg, globals())
    else:
        test = defaultTestLoader.loadTestsFromName(arg)
        result = _runner().run(test)
        sys.exit(not result.wasSuccessful())


def run_subprocess(args, options):
    from threading import Timer
    from mysubprocess import Popen, PIPE, STDOUT

    popen_args = [sys.executable, sys.argv[0], '--record',
                  '--runid', options.runid,
                  '--verbosity', options.verbosity]
    if options.db:
        popen_args += ['--db', options.db]
    popen_args += args
    popen_args = [str(x) for x in popen_args]
    if options.capture:
        popen = Popen(popen_args, stdout=PIPE, stderr=STDOUT, shell=False)
    else:
        popen = Popen(popen_args, shell=False)

    retcode = []

    def killer():
        retcode.append('TIMEOUT')
        print >> sys.stderr, 'Killing %s (%s) because of timeout' % (popen.pid, args)
        popen.kill()

    timeout = Timer(options.timeout, killer)
    timeout.start()
    output = ''
    output_printed = False
    try:
        try:
            if options.capture:
                while True:
                    data = popen.stdout.read(1)
                    if not data:
                        break
                    output += data
                    if options.verbosity >= 2:
                        sys.stdout.write(data)
                        output_printed = True
            retcode.append(popen.wait())
        except Exception:
            popen.kill()
            raise
    finally:
        timeout.cancel()
    # QQQ compensating for run_tests' screw up
    module_name = args[0]
    if module_name.endswith('.py'):
        module_name = module_name[:-3]
    output = output.replace(' (__main__.', ' (' + module_name + '.')
    return retcode[0], output, output_printed


def spawn_subprocess(args, options, base_params):
    success = False
    if options.db:
        module_name = args[0]
        if module_name.endswith('.py'):
            module_name = module_name[:-3]
        from datetime import datetime
        params = base_params.copy()
        params.update({'started_at': datetime.now(),
                       'test': module_name})
        row_id = store_record(options.db, 'test', params)
        params['id'] = row_id
    retcode, output, output_printed = run_subprocess(args, options)
    if len(output) > OUTPUT_LIMIT:
        warn = '<AbridgedOutputWarning>'
        output = output[:OUTPUT_LIMIT - len(warn)] + warn
    if retcode:
        if retcode == 1 and 'test_support.TestSkipped' in output:
            pass
        else:
            if not output_printed and options.verbosity >= -1:
                sys.stdout.write(output)
            print '%s failed with code %s' % (' '.join(args), retcode)
    elif retcode == 0:
        if not output_printed and options.verbosity >= 1:
            sys.stdout.write(output)
        if options.verbosity >= 0:
            print '%s passed' % ' '.join(args)
        success = True
    else:
        print '%s timed out' % ' '.join(args)
    if options.db:
        params['output'] = output
        params['retcode'] = retcode
        store_record(options.db, 'test', params)
    return success


def spawn_subprocesses(options, args):
    params = {'runid': options.runid,
              'python': '%s.%s.%s' % sys.version_info[:3],
              'changeset': get_changeset(),
              'libevent_version': get_libevent_version(),
              'uname': platform.uname()[0],
              'retcode': 'TIMEOUT'}
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
            success = spawn_subprocess(arg, options, params) and success
        except Exception:
            traceback.print_exc()
    if options.db:
        try:
            print '-' * 80
            if print_stats(options):
                success = False
        except sqlite3.OperationalError:
            traceback.print_exc()
        print 'To view stats again for this run, use %s --stats --runid %s --db %s' % (sys.argv[0], options.runid, options.db)
    if not success:
        sys.exit(1)


def get_testcases(cursor, runid, result=None):
    sql = 'select test, testcase from testcase where runid=?'
    args = (runid, )
    if result is not None:
        sql += ' and result=?'
        args += (result, )
    return ['.'.join(x) for x in cursor.execute(sql, args).fetchall()]


def get_failed_testcases(cursor, runid):
    sql = 'select test, testcase, result from testcase where runid=?'
    args = (runid, )
    sql += ' and result!="PASSED" and result!="TIMEOUT"'
    names = []
    errors = {}
    for test, testcase, result in cursor.execute(sql, args).fetchall():
        name = '%s.%s' % (test, testcase)
        names.append(name)
        errors[name] = result
    return names, errors


_warning_re = re.compile('\w*warning', re.I)


def get_warnings(output):
    """
    >>> get_warnings('hello DeprecationWarning warning: bla DeprecationWarning')
    ['DeprecationWarning', 'warning', 'DeprecationWarning']
    """
    if len(output) <= OUTPUT_LIMIT:
        return _warning_re.findall(output)
    else:
        return _warning_re.findall(output[:OUTPUT_LIMIT]) + ['AbridgedOutputWarning']


def get_exceptions(output):
    """
    >>> get_exceptions('''test$ python -c "1/0"
    ... Traceback (most recent call last):
    ...   File "<string>", line 1, in <module>
    ... ZeroDivisionError: integer division or modulo by zero''')
    ['ZeroDivisionError']
    """
    errors = []
    readtb = False
    for line in output.split('\n'):
        if 'Traceback (most recent call last):' in line:
            readtb = True
        else:
            if readtb:
                if line[:1] == ' ':
                    pass
                else:
                    errors.append(line.split(':')[0])
                    readtb = False
    return errors


def get_warning_stats(output):
    counter = {}
    for warning in get_warnings(output):
        counter.setdefault(warning, 0)
        counter[warning] += 1
    items = counter.items()
    items.sort(key=lambda (a, b): -b)
    result = []
    for name, count in items:
        if count == 1:
            result.append(name)
        else:
            result.append('%s %ss' % (count, name))
    return result


def get_ignored_tracebacks(test):
    if os.path.exists(test + '.py'):
        data = open(test + '.py').read()
        m = re.search('Ignore tracebacks: (.*)', data)
        if m is not None:
            return m.group(1).split()
    return []


def get_traceback_stats(output, test):
    ignored = get_ignored_tracebacks(test) or ignore_tracebacks
    counter = {}
    traceback_count = output.lower().count('Traceback (most recent call last)')
    ignored_list = []
    for error in get_exceptions(output):
        if error in ignored:
            ignored_list.append(error)
        else:
            counter.setdefault(error, 0)
            counter[error] += 1
        traceback_count -= 1
    items = counter.items()
    items.sort(key=lambda (a, b): -b)
    if traceback_count > 0:
        items.append(('other traceback', traceback_count))
    result = []
    for name, count in items:
        if count == 1:
            result.append('1 %s' % name)
        else:
            result.append('%s %ss' % (count, name))
    return result, ignored_list


def get_info(output, test):
    output = output[:OUTPUT_LIMIT]
    traceback_stats, ignored_list = get_traceback_stats(output, test)
    warning_stats = get_warning_stats(output)
    result = traceback_stats + warning_stats
    skipped = not warning_stats and not traceback_stats and ignored_list in [['test_support.TestSkipped'], ['test.test_support.TestSkipped']]
    return ', '.join(result), skipped


def print_stats(options):
    db = sqlite3.connect(options.db)
    cursor = db.cursor()
    if options.runid is None:
        options.runid = cursor.execute('select runid from test order by started_at desc limit 1').fetchall()[0][0]
        print 'Using the latest runid: %s' % options.runid
    total = len(get_testcases(cursor, options.runid))
    failed, errors = get_failed_testcases(cursor, options.runid)
    timedout = get_testcases(cursor, options.runid, 'TIMEOUT')
    for test, output, retcode in cursor.execute('select test, output, retcode from test where runid=?', (options.runid, )):
        info, skipped = get_info(output or '', test)
        if info:
            print '%s: %s' % (test, info)
        if retcode == 'TIMEOUT':
            for testcase in timedout:
                if testcase.startswith(test + '.'):
                    break
            else:
                timedout.append(test)
                total += 1
        elif retcode != 0:
            for testcase in failed:
                if testcase.startswith(test + '.'):
                    break
            else:
                if not skipped:
                    failed.append(test)
                    total += 1
    if failed:
        failed.sort()
        print 'FAILURES: '
        for testcase in failed:
            error = errors.get(testcase)
            if error:
                error = repr(error)[1:-1][:100]
                print ' - %s: %s' % (testcase, error)
            else:
                print ' - %s' % (testcase, )
    if timedout:
        print 'TIMEOUTS: '
        print ' - ' + '\n - '.join(timedout)
    print '%s testcases passed; %s failed; %s timed out' % (total, len(failed), len(timedout))
    if failed or timedout:
        return True
    return False


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', default=0, action='count')
    parser.add_option('-q', '--quiet', default=0, action='count')
    parser.add_option('--verbosity', default=0, type='int', help=optparse.SUPPRESS_HELP)
    parser.add_option('--db', default='testresults.sqlite3')
    parser.add_option('--no-db', dest='db', action='store_false')
    parser.add_option('--runid')
    parser.add_option('--record', default=False, action='store_true')
    parser.add_option('--no-capture', dest='capture', default=True, action='store_false')
    parser.add_option('--stats', default=False, action='store_true')
    parser.add_option('--timeout', default=DEFAULT_TIMEOUT, type=float, metavar='SECONDS')

    options, args = parser.parse_args()
    options.verbosity += options.verbose - options.quiet

    if options.db:
        if sqlite3:
            options.db = os.path.abspath(options.db)
            print 'Using the database: %s' % options.db
        else:
            sys.stderr.write('Cannot access the database %r: no sqlite3 module found.\n' % (options.db, ))
            options.db = False

    if options.db:
        db = sqlite3.connect(options.db)
        db.execute('create table if not exists test (id integer primary key autoincrement, runid text)')
        db.execute('create table if not exists testcase (id integer primary key autoincrement, runid text)')
        db.commit()

    if options.stats:
        print_stats(options)
    else:
        if not options.runid:
            try:
                import uuid
                options.runid = str(uuid.uuid4())
            except ImportError:
                import random
                options.runid = str(random.random())[2:]
            print 'Generated runid: %s' % (options.runid, )
        if options.record:
            run_tests(options, args)
        else:
            spawn_subprocesses(options, args)


if __name__ == '__main__':
    main()
