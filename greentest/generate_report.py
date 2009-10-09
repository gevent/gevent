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
import os
import traceback
try:
    import sqlite3
except ImportError:
    import pysqlite2.dbapi2 as sqlite3
from pprint import pprint

REPO_URL = 'http://bitbucket.org/denis/gevent'
row_def = ['testname']
column_def = ['changeset', 'python', 'libevent_version', 'libevent_method']
SQL = 'select * from testresult'


CSS = """
a.x
{
  color: black;
  text-decoration: none;
}

a.x:hover
{
  text-decoration: underline;
}

td.nodata
{
  align: center;
  bgcolor: gray;
}


table
{
  border: 1;
}

th
{
    font-weight: normal;
}

th.row
{
    text-align: left;
}
"""


def make_table(database, row, column):
    c = sqlite3.connect(database)
    res = c.execute((SQL))
    columns = [x[0].lower() for x in res.description]
    table = {}
    row_set = set()
    column_set = set()
    VARIES = object()
    common_fields = {}
    for values in res.fetchall():
        d = dict(zip(columns, values))
        for k, v in d.items():
            try:
                current_value = common_fields[k]
            except KeyError:
                common_fields[k] = v
            else:
                if current_value != v:
                    common_fields[k] = VARIES
        row_params = tuple(d[k] for k in row)
        column_params = tuple(d[k] for k in column)
        test_result = TestResult(**d)
        row_set.add(row_params)
        column_set.add(column_params)
        table.setdefault(row_params, {})[column_params] = test_result

        # columns totals
        table.setdefault(None, {}).setdefault(column_params, TestResult(0, 0, 0, 0)).__iadd__(test_result)

        # row totals
        table.setdefault(row_params, {}).setdefault(None, TestResult(0, 0, 0, 0)).__iadd__(test_result)

    common_fields = dict((k, v) for (k, v) in common_fields.items() if v is not VARIES)
    return table, sorted(row_set), sorted(column_set), common_fields


class TestResult:

    def __init__(self, runs, errors, fails, timeouts, exitcode=None, id=None, output=None, **ignore_kwargs):
        self.runs = max(int(runs), 0)
        self.errors = max(int(errors), 0)
        self.fails = max(int(fails), 0)
        self.timeouts = max(int(timeouts), 0)
        self.exitcode = int(exitcode) if exitcode is not None else None
        self.id = id
        self.output = output

    @property
    def passed(self):
        return max(0, self.runs - self.errors - self.fails)

    @property
    def failed(self):
        return self.errors + self.fails

    @property
    def total(self):
        return self.runs + self.timeouts

    @property
    def percentage(self):
        return float(self.passed) / self.total

    def __iadd__(self, other):
        self.runs += other.runs
        self.errors += other.errors
        self.fails += other.fails
        self.timeouts += other.timeouts
        if self.exitcode != other.exitcode:
            self.exitcode = None
        self.id = None
        self.output = None

    def color(self):
        if self.id is None:
            return 'white'
        if self.timeouts or self.exitcode in [7, 9, 10]:
            return 'red'
        elif self.errors or self.fails or self.exitcode:
            return 'yellow'
        else:
            return '"#72ff75"'

    def warnings(self):
        r = []
        if not self.failed and not self.timeouts:
            if self.exitcode in [7, 9, 10]:
                r += ['TIMEOUT']
            if self.exitcode:
                r += ['exitcode=%s' % self.exitcode]
            if self.output is not None:
                output = self.output.lower()
                warning = output.count('warning')
                if warning:
                    r += ['%s warnings' % warning]
                tracebacks = output.count('traceback (most recent call last):')
                if tracebacks:
                    r += ['%s tracebacks' % tracebacks]
        return r

    def text(self):
        errors = []
        if self.fails:
            errors += ['%s failed' % self.fails]
        if self.errors:
            errors += ['%s raised' % self.errors]
        if self.timeouts:
            errors += ['%s timeout' % self.timeouts]
        errors += self.warnings()
        if self.id is None:
            errors += ['<hr>%s total' % self.total]
        return '\n'.join(["%s passed" % self.passed] + errors).replace(' ', '&nbsp;')

    # shorter passed/failed/raised/timeout
    def text_short(self):
        r = '%s/%s/%s' % (self.passed, self.failed, self.timeouts)
        if self.warnings():
            r += '\n' + '\n'.join(self.warnings()).replace(' ', '&nbsp;')
        return r

    def __str__(self):
        text = self.text().replace('\n', '<br>\n')
        if self.id is None:
            valign = 'bottom'
        else:
            text = '<a class="x" href="output-%s.txt">%s</a>' % (self.id, text)
            valign = 'center'
        return '<td align=center valign=%s bgcolor=%s>%s</td>' % (valign, self.color(), text)

def format_table(table, row_def, rows, column_def, columns, common_fields):
    r = '<table border=1>\n'
    for index, header_row in enumerate(column_def):
        r += '<tr>\n'
        r += '<th/>' * len(row_def)
        for column in columns:
            field_name = column_def[index]
            field_value = column[index]
            if field_name not in common_fields:
                r += '<th>%s</th>\n' % decorate(field_name, field_value, common_fields)
        r += '</tr>\n'
    for row in [None, ] + rows:
        r += '<tr>\n'
        if row is None:
            r += '<th class=row colspan=%s>Total</th>' % len(row_def)
        else:
            for row_def_item, row_item in zip(row_def, row):
                row_item = decorate(row_def_item, row_item, common_fields)
                r += '<th class=row>%s</th>\n' % row_item
        for column in columns:
            try:
                r += '%s\n' % table[row][column]
            except KeyError:
                r += '<td align=center bgcolor=gray>no data</td>'
        r += '</tr>\n'
    r += '</table>\n'
    return r

def decorate(field_name, field_value, common_fields):
    d = globals().get('decorate_%s' % field_name)
    if d is not None:
        try:
            return d(field_value, common_fields)
        except KeyError, ex:
            pass
        except Exception:
            traceback.print_exc()
    return field_value

def decorate_testname(testname, common_fields):
    return '<a href="%s/src/%s/greentest/%s">%s</a>' % (REPO_URL, common_fields['changeset'].rstrip('+').split('_')[1], testname, testname)

def decorate_changeset(changeset, common_fields=None, frmt_text='%(rev)s%(nonclean)s'):
    nonclean = changeset.endswith('+')
    nonclean = '<b>+</b>' if nonclean else ''
    rev, hash = changeset.rstrip('+').split('_')
    url = '%s/changeset/%s' % (REPO_URL, hash)
    text = frmt_text % locals()
    return '<a href="%s">%s</a>' % (url, text)

def format_header_common_fields(fields):
    result = ''
    changeset = fields.get('changeset')
    if changeset is not None:
        result += decorate_changeset(changeset, frmt_text='gevent_changeset: %(rev)s%(nonclean)s') + '<br>\n'
    python = fields.get('python')
    if python is not None:
        result += 'Python version: %s<br>\n' % python
    if fields.get('libevent_version'):
        result += 'Libevent version: %s<br>\n' % fields['libevent_version']
    if fields.get('libevent_method'):
        result += 'Libevent method: %s<br>\n' % fields['libevent_method']
    result += '<br>\n'
    return result

def format_html(table, common_fields):
    r = '<html><head><style type="text/css">%s</style></head><body>' % CSS
    x = format_header_common_fields(common_fields)
    r += x
    r += table
    r += '<br><br></body></html>'
    return r

def generate_raw_results(path, database):
    c = sqlite3.connect(database)
    res = c.execute('select id, output from testresult').fetchall()
    for id, out in res:
        filename = os.path.join(path, 'output-%s.txt' % id)
        if not os.path.exists(filename):
            file(filename, 'w').write(out.encode('utf-8'))
            sys.stderr.write('.')
    sys.stderr.write('\n')

def main(db):
    path = os.path.dirname(db)
    file_path = os.path.join(path, 'index.html')
    print '%s: generating %s' % (db, file_path)
    table, rows, columns, common_fields = make_table(db, row=row_def, column=column_def)
    if common_fields:
        pprint(common_fields) # this fields are the same for every item processed
    for field in ['runs', 'errors', 'fails', 'timeouts', 'exitcode', 'id', 'output']:
        common_fields.pop(field, None)

    table = format_table(table, row_def, rows, column_def, columns, common_fields)
    report = format_html(table, common_fields)

    try:
        os.makedirs(path)
    except OSError, ex:
        if 'File exists' not in str(ex):
            raise
    file(file_path, 'w').write(report)
    print '%s: written %s: %s rows x %s columns' % (db, file_path, len(rows), len(columns))
    generate_raw_results(path, db)

if __name__=='__main__':
    if not sys.argv[1:]:
        from record_results import get_results_db
        db = get_results_db()
        sys.argv.append(db)
    for db in sys.argv[1:]:
        main(db)

