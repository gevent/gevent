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
import codecs
from os.path import abspath, dirname, join, split
try:
    import sqlite3
except ImportError:
    import pysqlite2.dbapi2 as sqlite3
import warnings
from greentest import disabled_marker

warnings.simplefilter('ignore')

def get_results_db():
    path = join(join(*split(dirname(abspath(__file__)))[:-1]), 'testresults')
    try:
        os.makedirs(path)
    except OSError:
        pass
    return join(path, 'results.db')

def record(argv, stdout, returncode):
    path = get_results_db()
    c = sqlite3.connect(path)
    c.execute('''create table if not exists command_record
              (id integer primary key autoincrement,
               command text,
               stdout text,
               exitcode integer)''')
    c.execute('insert into command_record (command, stdout, exitcode)'
              'values (?, ?, ?)', (`argv`, stdout, returncode))
    c.commit()

def main():
    argv = sys.argv[1:]
    if argv[0]=='-d':
        debug = True
        del argv[0]
    else:
        debug = False
    output_name = os.tmpnam()
    arg = ' '.join(argv) + ' &> %s' % output_name
    print arg
    returncode = os.system(arg)>>8
    print arg, 'finished with code', returncode
    stdout = codecs.open(output_name, mode='r', encoding='utf-8', errors='replace').read().replace('\x00', '?')
    if not debug:
        if returncode==1:
            pass
        elif returncode==8 and disabled_marker in stdout:
            pass
        else:
            record(argv, stdout, returncode)
            os.unlink(output_name)
    sys.exit(returncode)

if __name__=='__main__':
    main()

