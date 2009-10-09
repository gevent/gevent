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

PARSER_VERSION=1
param_re = re.compile('^===(\w+)=(.*)$', re.M)

def parse_output(s):
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
    try:
        c.execute('''alter table testresult add column parser_version integer default -1''')
        c.commit()
    except sqlite3.OperationalError, ex:
        if 'duplicate column' not in str(ex).lower():
            raise

    parse_error = 0

    SQL = 'select id, command, output, exitcode from testresult'
    if not options.redo:
        SQL += ' where parser_version!=%s' % PARSER_VERSION
    count = 0
    try:
        for row in c.execute(SQL).fetchall():
            id, command, output, exitcode = row
            try:
                params = parse_output(output)
                if greentest_delim in output and unittest_re.search(output) is not None:
                    runs, errors, fails, timeouts = parse_greentest_output(output)
                else:
                    if exitcode == 0:
                        runs, errors, fails, timeouts = 1,0,0,0
                    if exitcode == 7:
                        runs, errors, fails, timeouts = 0,0,0,1
                    elif exitcode:
                        runs, errors, fails, timeouts = 1,1,0,0
            except Exception:
                traceback.print_exc()
                sys.stderr.write('Failed to parse id=%s\n\n' % id)
                parse_error += 1
            else:
                added_columns = set()
                params['parser_version'] = PARSER_VERSION
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
                            c.execute('''alter table testresult add column %s text''' % key)
                            c.commit()
                        except sqlite3.OperationalError, ex:
                            if 'duplicate column' not in str(ex).lower():
                                raise
                sql = 'update testresult set %s where id=%s' % (', '.join('%s=?' % x for x in keys), id)
                c.execute(sql, values)
                c.commit()
                count += 1
    finally:
        msg = '%s: %s row%s updated' % (db, count, 's' if count!=1 else '')
        if parse_error:
            msg += ', %s error%s' % (parse_error, 's' if parse_error!=1 else '')
        print msg
    return count

if __name__=='__main__':
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('--redo', action='store_true', default=False)
    options, args = parser.parse_args()
    if not args:
        from record_results import get_results_db
        db = get_results_db()
        args.append(db)
    for db in args:
        if main(db, options):
            import generate_report
            generate_report.main(db)

