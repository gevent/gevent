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

"""Run all the tests"""
import sys
import os
import random
from glob import glob
from optparse import OptionParser
from time import time

COMMAND = sys.executable + ' ./record_results.py ' + sys.executable + ' ./with_timeout.py %(test)s'
PARSE_PERIOD = 10

def w(s):
    sys.stderr.write("%s\n" % (s, ))

def enum_tests():
    tests = []
    tests += glob('test_*.py')
    tests += glob('*_test.py')
    tests = set(tests) - set(['test_support.py'])
    return tests

def cmd(program):
    w(program)
    res = os.system(program)>>8
    w(res)
    if res==1:
        sys.exit(1)
    return res

def main():
    parser = OptionParser()
    parser.add_option('--skip', action='store_true', default=False,
                      help="Run all the tests except those provided on command line")
    parser.add_option('--dry-run')
    options, tests = parser.parse_args()
    if options.skip:
        tests = enum_tests() - set(tests)
    elif not tests:
        tests = enum_tests()

    tests = list(tests)
    random.shuffle(tests)
    print 'tests: %s' % ','.join(tests)

    if options.dry_run:
       return

    last_time = time()

    for test in tests:
        w(test)
        cmd(COMMAND % locals())
        if time()-last_time>PARSE_PERIOD:
            os.system('./parse_results.py')
            last_time = time()
    os.system('./parse_results.py')

if __name__=='__main__':
    main()

