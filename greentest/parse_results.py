#!/usr/bin/python
# Copyright (c) 2008-2009 AG Projects
# Author: Denis Bilenko
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import sys
import traceback
import sqlite3
import re

param_re = re.compile('^===(\w+)=(.*)$', re.M)

def parse_stdout(s):
    argv = re.search('^===ARGV=(.*?)$', s, re.M).group(1)
    argv = argv.split()
    testname = argv[-1]
    params = {'testname': testname}
    for m in param_re.finditer(s):
        key, val = m.groups()
        params[key] = val
    return params

greentest_delim = '----------------------------------------------------------------------'
unittest_re = re.compile('^Ran (\d+) test.*?$', re.M)

def parse_greentest_output(s):
    s = s[s.rindex(greentest_delim)+len(greentest_delim):]
    num = int(unittest_re.search(s).group(1))
    ok = re.search('^OK$', s, re.M)
    error, fail, timeout = 0, 0, 0
    failed_match = re.search(r'^FAILED \((?:failures=(?P<f>\d+))?,? ?(?:errors=(?P<e>\d+))?\)$', s, re.M)
    ok_match = re.search('^OK$', s, re.M)
    if failed_match:
        assert not ok_match, (ok_match, s)
        fail = failed_match.group('f')
        error = failed_match.group('e')
        fail = int(fail or '0')
        error = int(error or '0')
    else:
        assert ok_match, `s`
    timeout_match = re.search('^===disabled because of timeout: (\d+)$', s, re.M)
    if timeout_match:
        timeout = int(timeout_match.group(1))
    return num, error, fail, timeout

def main(db, options):
    print '%s: parsing output' % db
    c = sqlite3.connect(db)
    c.execute('''create table if not exists parsed_command_record (id integer not null unique)''')
    c.commit()

    parse_error = 0

    SQL = 'select command_record.id, command, stdout, exitcode from command_record'
    if not options.redo:
        SQL += ' where not exists (select * from parsed_command_record where parsed_command_record.id=command_record.id)'
    for row in c.execute(SQL).fetchall():
        id, command, stdout, exitcode = row
        try:
            params = parse_stdout(stdout)
            if greentest_delim in stdout and unittest_re.search(stdout) is not None:
                runs, errors, fails, timeouts = parse_greentest_output(stdout)
            else:
                if exitcode == 0:
                    runs, errors, fails, timeouts = 1,0,0,0
                if exitcode == 7:
                    runs, errors, fails, timeouts = 0,0,0,1
                elif exitcode:
                    runs, errors, fails, timeouts = 1,1,0,0
        except Exception:
            parse_error += 1
            sys.stderr.write('Failed to parse id=%s\n' % id)
            print repr(stdout)
            traceback.print_exc()
        else:
            added_columns = set()
            #print id, runs, errors, fails, timeouts, params
            params['id'] = id
            params['runs'] = runs
            params['errors'] = errors
            params['fails'] = fails
            params['timeouts'] = timeouts
            items = params.items()
            keys = [x[0].lower() for x in items]
            values = [x[1] for x in items]
            for key in keys:
                if key not in added_columns:
                    added_columns.add(key)
                    try:
                        c.execute('''alter table parsed_command_record add column %s text''' % key)
                        c.commit()
                    except sqlite3.OperationalError, ex:
                        if 'duplicate column' not in str(ex).lower():
                            raise
            sql = 'insert or replace into parsed_command_record (%s) values (%s)' % (', '.join(keys), ', '.join(['?']*len(items)))
            #print sql
            c.execute(sql, values)
            c.commit()

if __name__=='__main__':
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--redo', action='store_true', default=False)
    options, args = parser.parse_args()
    if not args:
        from greentest.record_results import get_results_db
        db = get_results_db()
        args.append(db)
    for db in args:
        main(db, options)
        from greentest import generate_report
        generate_report.main(db)

