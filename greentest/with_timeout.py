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

"""
Run Python script in a child process. Kill it after timeout has elapsed.
If the script was running greentest test cases, the timeouted test case is
disabled and the script is restarted.

Usage: %prog [-t TIMEOUT] program.py [args]

If program.py timed out, return 7
If program.py exited with non-zero value, return 8
If program.py exited with zero value after several runs, return 9
If program.py exited with non-zero value after several runs, return 10
"""
import sys
import os
import time
import warnings

if sys.argv[1:2] and sys.argv[1]=='-t':
    del sys.argv[1]
    TIMEOUT = int(sys.argv[1])
    del sys.argv[1]
else:
    TIMEOUT = 20

try:
    disabled_tests
except NameError:
    disabled_tests = []

try:
    CURRENT_TEST_FILENAME
except NameError:
    warnings.filterwarnings('ignore', 'tmpnam is a potential security risk to your program')
    CURRENT_TEST_FILENAME = os.tmpnam()
    del warnings.filters[0]

class Alarm(Exception):
    pass

def al(*args):
    raise Alarm

def _test():
    """
    >>> system('./with_timeout.py -t 3 __init__.py')
    (0, 0)

    >>> system('./with_timeout.py -t 3 /usr/lib/python2.5/BaseHTTPServer.py 0')
    (7, 3)

    >>> system('./with_timeout.py -t 3 with_timeout.py --selftest1')
    (9, 3)

    >>> system('./with_timeout.py -t 3 with_timeout.py --selftest2')
    (10, 3)

    >>> system('./with_timeout.py -t 3 with_timeout.py no_such_file.xxx')
    (8, 0)
    """
    import doctest
    doctest.testmod()

if not sys.argv[1:]:
    def system(*args):
        start = time.time()
        res = os.system(*args)
        return res>>8, int(time.time()-start)
    #system('./with_timeout.py -t 3 with_timeout.py selftest')
    #sys.exit(0)
    _test()
    sys.exit(__doc__.replace('%prog', sys.argv[0]))
elif sys.argv[1:]==['--selftest1']:
    import greentest
    class Test(greentest.TestCase):
        def test1(self):
            pass
        def test_long(self):
            time.sleep(10)
    import test_support
    test_support.run_unittest(Test)
    sys.exit(0)
elif sys.argv[1:]==['--selftest2']:
    import greentest
    class Test(greentest.TestCase):
        def test_fail(self):
            fail
        def test_long(self):
            time.sleep(10)
    import test_support
    test_support.run_unittest(Test)
    sys.exit(0)

filename = sys.argv[1]
del sys.argv[0]

def execf():
    #print 'in execf', disabled_tests
    def patch_greentest():
        "print test name before it was run and write it pipe"
        import greentest
        class TestCase(greentest.TestCase):
            base = greentest.TestCase
            def run(self, result=None):
                try:
                    testMethodName = self._testMethodName
                except:
                    testMethodName = self.__testMethodName
                name = "%s.%s" % (self.__class__.__name__, testMethodName)
                if name in disabled_tests:
                    return
                print name, ' '
                sys.stdout.flush()
                file(CURRENT_TEST_FILENAME, 'w').write(name)
                try:
                    return self.base.run(self, result)
                finally:
                    sys.stdout.flush()
                    try:
                        os.unlink(CURRENT_TEST_FILENAME)
                    except:
                        pass
        greentest.TestCase = TestCase
    patch_greentest()
    execfile(filename, globals())

while True:
    #print 'before fork, %s' % disabled_tests
    try:
        os.unlink(CURRENT_TEST_FILENAME)
    except:
        pass
    child = os.fork()
    if child == 0:
        print '===PYTHON=%s.%s.%s' % sys.version_info[:3]
        print '===ARGV=%s' % ' '.join(sys.argv)
        print '===TIMEOUT=%r' % TIMEOUT
        import gevent
        from gevent import __version__
        from gevent import core
        print '===VERSION=%s' % __version__
        print '===PATH=%s' % gevent.__file__
        try:
            diffstat = os.popen(r"hg diff 2> /dev/null | diffstat -q").read().strip()
        except:
            diffstat = None
        try:
            changeset = os.popen(r"hg log -r tip 2> /dev/null | grep changeset").readlines()[0].replace('changeset:', '').strip().replace(':', '_')
            if diffstat:
                changeset += '+'
            print '===CHANGESET=%s' % changeset
        except:
            changeset = ''
        libevent_version = core.get_version()
        if core.get_header_version() != core.get_version() and core.get_header_version() is not None:
            libevent_version += '/headers=%s' % core.get_header_version()
        print '===LIBEVENT_VERSION=%s' % libevent_version
        print '===LIBEVENT_METHOD=%s' % core.get_method()
        if diffstat:
            print 'Non-clean working directory:'
            print '-' * 80
            print diffstat
            print '-' * 80
        sys.stdout.flush()
        execf()
        break
    else:
        start = time.time()
        import signal
        signal.signal(signal.SIGALRM, al)
        signal.alarm(TIMEOUT)
        pid = None
        try:
            pid, status = os.waitpid(child, 0)
            signal.alarm(0)
        except Alarm:
            try:
                os.kill(child, signal.SIGKILL)
            except Exception:
                pass
            print '\n===%s was killed after %s seconds' % (child, time.time()-start)
            sys.stdout.flush()
            bad_test = None
            try:
                bad_test = file(CURRENT_TEST_FILENAME).read()
            except IOError:
               pass
            if bad_test in disabled_tests:
                print '\n===%s was disabled but it still managed to fail?!' % bad_test
                sys.stdout.flush()
                break
            if bad_test is None:
                sys.exit(7)
            print '\n===Trying again, now without %s' % bad_test
            sys.stdout.flush()
            disabled_tests.append(bad_test)
        except:
            try:
                signal.alarm(0)
            except:
                pass
            try:
                os.kill(child, signal.SIGKILL)
            except:
                pass
            raise
        else:
            print '===%s exited with code %s' % (pid, status)
            sys.stdout.flush()
            if disabled_tests:
                print '\n===disabled because of timeout: %s\n%s\n' % (len(disabled_tests), '\n'.join(disabled_tests))
                sys.stdout.flush()
            if disabled_tests:
                if status:
                    retcode = 10
                else:
                    retcode = 9
            else:
                if status:
                    retcode = 8
                else:
                    retcode = 0
            sys.exit(retcode)

