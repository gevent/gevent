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

import greentest
from gevent import spawn, coros
from greentest import TestCase

class TestSemaphore(TestCase):

    def test_bounded(self):
        sem = coros.BoundedSemaphore(2, limit=3)
        self.assertEqual(sem.acquire(), True)
        self.assertEqual(sem.acquire(), True)
        spawn(sem.release)
        self.assertEqual(sem.acquire(), True)
        self.assertEqual(-3, sem.balance)
        sem.release()
        sem.release()
        sem.release()
        spawn(sem.acquire)
        sem.release()
        self.assertEqual(3, sem.balance)

    def test_bounded_with_zero_limit(self):
        sem = coros.BoundedSemaphore(0, 0)
        spawn(sem.acquire)
        sem.release()


if __name__=='__main__':
    greentest.main()
