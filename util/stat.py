#!/usr/bin/python
import sys
import os
import traceback
import sqlite3
import pprint
try:
    from ast import literal_eval
except ImportError:
    literal_eval = eval


DB = None
parameters = {}
interesting_columns = []
ignore_columns = ['started_at',
                  'version',
                  'recommended_backends',
                  'supported_backends']


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


def execute(sql, args=None, noisy=True):
    if DB is None:
        return ()
    try:
        if args is None:
            result = DB.execute(sql)
        else:
            result = DB.execute(sql, args)
    except Exception, ex:
        if noisy and 'no such column' not in str(ex):
            log('FAILED query %r %s: %s: %s', sql, args or '', type(ex).__name__, ex)
        raise
    else:
        DB.commit()
        return result


def mk_testcase(module, testcase):
    if testcase:
        return module + '.' + testcase
    else:
        return module


def get_module(test_id):
    result = execute('SELECT module FROM test WHERE test_id=?', (test_id, )).fetchall()
    assert len(result) == 1 and len(result[0]) == 1, result
    return result[0][0]


def get_columns(table):
    return [x[1] for x in execute('PRAGMA table_info(%s)' % table).fetchall()]


def remove_dependent_columns(main_columns, dependent_columns):
    main_columns = ', '.join(main_columns)
    n_versions = len(execute('select distinct %s from run' % main_columns).fetchall())
    for dependent_column in dependent_columns:
        remove_column = False
        try:
            sql = 'select distinct %s, %s from run' % (main_columns, dependent_column)
            cursor = execute(sql)
        except sqlite3.OperationalError, ex:
            if str(ex) == 'no such column: %s' % dependent_column:
                remove_column = True
            else:
                raise
        else:
            remove_column = len(cursor.fetchall()) == n_versions
        if remove_column:
            try:
                interesting_columns.remove(dependent_column)
            except ValueError:
                pass


def format_runs(runs, allruns):
    if len(runs) <= 3:
        return ', '.join(format_run(x) for x in runs)
    passed = set(allruns) - set(runs)
    if not passed:
        return 'all'
    if len(passed) < len(runs) - 1 and len(passed) <= 3:
        return 'all except ' + ', '.join(format_run(x) for x in passed)
    return ', '.join(format_run(x) for x in runs)


def format_run(run_id):
    result = ''
    if interesting_columns:
        sql = 'SELECT %s FROM run WHERE run_id=?' % ', '.join(interesting_columns)
        data = dict(zip(interesting_columns, [shorten(x) for x in execute(sql, (run_id, )).fetchone()]))
    else:
        data = {}
    python_version = data.pop('python_version', None)
    if python_version is not None:
        result = python_version
        python_exe = data.pop('python_exe', None)
        if python_exe:
            if python_exe == '/usr/bin/python' + python_version[:3]:
                pass
            elif python_exe == '/usr/bin/python' + python_version[:3] + '-dbg':
                result += '-dbg'
            else:
                data['exe'] = python_exe
    for key, value in data.items():
        if value is None:
            data.pop(key)
    result += ' ' + ' '.join('%s=%s' % item for item in sorted(data.items()))
    result = result.strip()
    return result or 'default'


def ascii(s):
    try:
        return s.encode('ascii')
    except Exception:
        return s


def flatten(items):
    for item in items:
        if isinstance(item, basestring):
            yield item
        else:
            try:
                iter(item)
            except TypeError:
                yield item
            else:
                for x in flatten(item):
                    yield x


def shorten(x):
    if not isinstance(x, basestring):
        return x
    try:
        x = literal_eval(x)
    except Exception:
        return x
    try:
        iter(x)
    except TypeError:
        return x
    items = list(flatten(x))
    items = [str(x) for x in items]
    items = [x for x in items if x]
    return '/'.join(items)


def main():
    global DB, parameters, interesting_columns
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-q', '--quiet', action='store_true')
    options, args = parser.parse_args()

    [database] = args
    DB = sqlite3.connect(database)

    for column in sorted(get_columns('run')):
        if column in ignore_columns:
            continue
        result = execute('select distinct ' + column + ' from run').fetchall()
        values = set([ascii(x[0]) for x in result])
        values = list(set([shorten(x) for x in values]))
        if column == 'run_id':
            def get_started_at(run_id):
                return execute('select started_at from run where run_id=?', (run_id, )).fetchone()[0]
            values.sort(key=get_started_at)
        parameters[column] = values

    #pprint.pprint(parameters)
    interesting_columns = parameters.keys()

    remove_dependent_columns(['python_version',
                              'python_exe',
                              'system'],
                             ['python_build',
                              'python_implementation',
                              'libc_ver',
                              'linux_distribution'])

    remove_dependent_columns(['python_version', 'system'], ['python_exe'])

    allruns = parameters['run_id']

    print 'Common:'

    for key, values in sorted(parameters.items()):
        if len(values) == 1:
            parameters.pop(key)
            value = values[0]
            if value:
                print '  %s: %s' % (key, value)
            if key in interesting_columns:
                interesting_columns.remove(key)
    print

    for run_id in allruns:
        n_total = execute('SELECT count(*) FROM testcase WHERE run_id=?', (run_id, )).fetchone()[0]
        n_failed = execute('SELECT count(*) FROM testcase WHERE run_id=? AND result!="PASSED"', (run_id, )).fetchone()[0]
        if not n_failed and n_total:
            info = 'passed'
        else:
            info = '%s failed out of %s' % (n_failed, n_total)
        print '%s: %s' % (format_run(run_id), info)
    print

    sql = 'SELECT run_id, test_id, testcase FROM testcase WHERE result!="PASSED" ORDER BY test_id'
    results = {}

    for run_id, test_id, testcase in execute(sql).fetchall():
        module = get_module(test_id)
        testcase = mk_testcase(module, testcase)
        results.setdefault(testcase, []).append(run_id)

    results = results.items()

    def score(runs):
        return -len(runs)

    # will print the most important failures first
    # a test case failing in all runs is the most important
    results.sort(key=lambda (testcase, runs): score(runs))

    testcases = {}

    for testcase, runs in results:
        testcases.setdefault(tuple(runs), []).append(testcase)

    testcases = testcases.items()
    testcases.sort(key=lambda (key, value): score(key))

    for runs, cases in testcases:
        print 'Fail in %s:' % format_runs(runs, allruns)
        for case in sorted(cases):
            print '  ', case
        print


if __name__ == '__main__':
    try:
        main()
    except sqlite3.OperationalError, ex:
        sys.exit('%s: Exiting because of %s: %s' % (os.path.basename(sys.argv[0]), type(ex).__name__, ex))
