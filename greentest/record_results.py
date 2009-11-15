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

"""Run the program and record stdout/stderr/exitcode into the database results.rev_changeset.db

Usage: %prog program [args]
"""
import sys
import os
import subprocess
from os.path import abspath, dirname, join, split
try:
    import sqlite3
except ImportError:
    try:
        import pysqlite2.dbapi2 as sqlite3
    except ImportError:
        sqlite3 = None
        print "sqlite3 not installed, won't record the results in the database"
import warnings
from greentest import disabled_marker

warnings.simplefilter('ignore')

path = join(join(*split(dirname(abspath(__file__)))[:-1]), 'testresults')

def get_results_db():
    try:
        os.makedirs(path)
    except OSError:
        pass
    return join(path, 'results.db')

if sqlite3 is None:

    def record(argv, output, returncode):
        print output
        print 'returncode=%s' % returncode

else:

    def record(argv, output, returncode):
        print "saving %s bytes of output; returncode=%s" % (len(output), returncode)
        path = get_results_db()
        c = sqlite3.connect(path)
        c.execute('''create table if not exists testresult
                  (id integer primary key autoincrement,
                   command text,
                   output text,
                   exitcode integer)''')
        c.execute('insert into testresult (command, output, exitcode)'
                  'values (?, ?, ?)', (`argv`, output, returncode))
        c.commit()

def main():
    argv = sys.argv[1:]
    if argv[0]=='-d':
        debug = True
        del argv[0]
    else:
        debug = False
    arg = ' '.join(argv)
    print arg
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    returncode = p.wait()
    output = p.stdout.read()
    if not debug:
        if returncode==1:
            pass
        elif returncode==8 and disabled_marker in output:
            pass
        else:
            record(argv, output, returncode)
    sys.exit(returncode)

if __name__=='__main__':
    main()

