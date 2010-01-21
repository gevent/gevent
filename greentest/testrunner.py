#!/usr/bin/python
"""Unit test runner.

This test runner runs individual test modules within a subprocess, thus allowing them to
mangle globals on the module level freely (i.e. do monkey patching).

To report the results and generate statistics sqlite3 database is used.

Additionally, the subprocess is killed after a timeout has passed. The test case remains
in the database logged with the result 'TIMEOUT'.

The --db option, when provided, specifies sqlite3 database that holds the test results.
By default 'testresults.sqlite3' is used in the current directory.
If the a mercurial repository is detected and it is "dirty", that is, has uncommited changes
then '/tmp/testresults.sqlite3' is used, which is cleaned up before each run.

The results are stored in the following 2 tables:

testcase:

  runid   | test   | testcase        | result             | time |
  --------+--------+-----------------+--------------------+------+
  abc123  | module | class.function  | PASS|FAIL|TIMEOUT  | 0.01 |

test:

  runid   | test    | python | output | retcode | changeset   | uname | started_at |
  --------+---------+--------+--------+---------+-------------+-------+------------+
  abc123  | module  | 2.6.4  | ...    |       1 | 123_fe43ca+ | Linux |            |

Set runid with --runid option. It must not exists in the database. The random
one will be selected if not provided.
"""

DEFAULT_TIMEOUT = 20

import sys
import os
from unittest import _TextTestResult, defaultTestLoader, TextTestRunner
import platform

try:
    import sqlite3
except ImportError:
    try:
        import pysqlite2.dbapi2 as sqlite3
    except ImportError:
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
        self._store_result(test, 'PASS')

    def addError(self, test, err):
        _TextTestResult.addError(self, test, err)
        self._store_result(test, 'FAIL')

    def addFailure(self, test, err):
        _TextTestResult.addFailure(self, test, err)
        self._store_result(test, 'FAIL')


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
        diffstat = os.popen(r"hg diff 2> /dev/null | diffstat -q").read().strip()
    except Exception:
        diffstat = None
    try:
        changeset = os.popen(r"hg log -r tip 2> /dev/null | grep changeset").readlines()[0]
        changeset = changeset.replace('changeset:', '').strip().replace(':', '_')
        if diffstat:
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


def get_libevent_method():
    from gevent import core
    return core.get_method()


def get_tempnam():
    import warnings
    warnings.filterwarnings('ignore', 'tempnam is a potential security risk to your program')
    tempnam = os.tempnam()
    del warnings.filters[0]
    database_path = os.path.join(os.path.dirname(tempnam), 'testresults.sqlite3')
    try:
        os.unlink(database_path)
    except OSError:
        pass
    return database_path


def run_tests(options, args):
    if len(args) != 1:
        sys.exit('--record only supports one module at a time')
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
    if os.path.exists(arg):
        sys.argv = args
        execfile(arg, globals())
    else:
        test = defaultTestLoader.loadTestsFromName(arg)
        result = _runner().run(test)
        sys.exit(not result.wasSuccessful())


def run_subprocess(arg, options):
    from subprocess import Popen, PIPE, STDOUT
    from threading import Timer
    popen_args = [sys.executable, sys.argv[0], '--record',
                  '--runid', options.runid,
                  '--verbosity', options.verbosity,
                  '--db', options.db,
                  arg]
    popen_args = [str(x) for x in popen_args]
    if options.capture:
        popen = Popen(popen_args, stdout=PIPE, stderr=STDOUT)
    else:
        popen = Popen(popen_args)
    def killer():
        print >> sys.stderr, 'Killing %s' % popen.pid
        popen.terminate()
    timeout = Timer(options.timeout, killer)
    timeout.start()
    try:
        if options.capture:
            output = popen.stdout.read()
        else:
            output = ''
        retcode = popen.wait()
    except:
        popen.terminate()
        raise
    finally:
        timeout.cancel()
    return retcode, output


def spawn_subprocesses(options, args):
    if options.db:
        db = sqlite3.connect(options.db)
        cursor = db.cursor()
        results = cursor.execute('select * from test where runid=?', (options.runid, )).fetchall() or \
                  cursor.execute('select * from testcase where runid=?', (options.runid, )).fetchall()
        if results:
            sys.exit('Entries with such runid already exists')
    uname = platform.uname()[0]
    for arg in args:
        if options.db:
            module_name = arg
            if module_name.endswith('.py'):
                module_name = module_name[:-3]
                from datetime import datetime
            params = {'started_at': datetime.now(),
                      'runid': options.runid,
                      'test': module_name,
                      'python': '%s.%s.%s' % sys.version_info[:3],
                      'changeset': get_changeset(),
                      'libevent_version': get_libevent_version(),
                      'libevent_method': get_libevent_method(),
                      'uname': uname}
        retcode, output = run_subprocess(arg, options)
        if retcode:
            sys.stdout.write(output)
            print '%s failed with code %s' % (arg, retcode)
        elif retcode == 0:
            if options.verbosity > 0:
                sys.stdout.write(output)
            print '%s passed' % arg
        else:
            print '%s timed out' % arg
        if options.db:
            params['output'] = output
            params['retcode'] = retcode
            store_record(options.db, 'test', params)
    if options.db:
        print_stats(options)
    print 'To view stats again for this run, use %s --stats --runid %s --db %s' % (sys.argv[0], options.runid, options.db)


def print_stats(options):
    db = sqlite3.connect(options.db)
    cursor = db.cursor()
    try:
        total = len(cursor.execute('select test, testcase from testcase where runid=?', (options.runid, )).fetchall())
    except sqlite3.OperationalError:
        return
    sql = 'select test, testcase from testcase where runid=? and result="%s"'
    failed = ['.'.join(x) for x in cursor.execute(sql % 'FAIL', (options.runid, )).fetchall()]
    timedout = ['.'.join(x) for x in cursor.execute(sql % 'TIMEOUT', (options.runid, )).fetchall()]
    if failed:
        print 'FAILURES: '
        print ' - ' + '\n - '.join(failed)
    if timedout:
        print 'TIMEOUTS: '
        print ' - ' + '\n - '.join(timedout)
    warning_reports = []
    for test, output in cursor.execute('select test, output from test where runid=?', (options.runid, )):
        output_lower = output.lower()
        warnings = output_lower.count('warning')
        tracebacks = output_lower.count('traceback')
        if warnings or tracebacks:
            warning_reports.append((test, warnings, tracebacks))
    if warning_reports:
        print 'WARNINGS: '
        for test, warnings, tracebacks in warning_reports:
            print ' - %s' % test,
            if warnings:
                print '%s warnings; ' % warnings,
            if tracebacks:
                print '%s tracebacks; ' % tracebacks,
            print
    print '%s testcases passed; %s failed; %s timed out' % (total, len(failed), len(timedout))


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose', default=0, action='count')
    parser.add_option('-q', '--quiet', default=0, action='count')
    parser.add_option('--verbosity', default=0, type='int', help=optparse.SUPPRESS_HELP)
    parser.add_option('--db')
    parser.add_option('--runid')
    parser.add_option('--record', default=False, action='store_true')
    parser.add_option('--no-capture', dest='capture', default=True, action='store_false')
    parser.add_option('--stats', default=False, action='store_true')
    parser.add_option('--timeout', default=DEFAULT_TIMEOUT, type=float, metavar='SECONDS')

    options, args = parser.parse_args()
    options.verbosity += options.verbose - options.quiet

    if options.db is None and sqlite3:
        options.db = get_tempnam() if get_changeset().endswith('+') else 'testresults.sqlite3'
        print 'Storing the results in %s' % options.db
    elif options.db and not sqlite3:
        sys.exit('Cannot access the database: no sqlite3 module found.')

    if options.db:
        db = sqlite3.connect(options.db)
        db.execute('create table if not exists test (id integer primary key autoincrement, runid text)')
        db.execute('create table if not exists testcase (id integer primary key autoincrement, runid text)')
        db.commit()

    if options.stats:
        print_stats(options)
    else:
        if not options.runid:
            import uuid
            options.runid = str(uuid.uuid4())
            print 'Generated runid: %s' % (options.runid, )
        if options.record:
            run_tests(options, args)
        elif args:
            spawn_subprocesses(options, args)
        else:
            sys.exit('Please provide at least one module to run.')


if __name__ == '__main__':
    main()
