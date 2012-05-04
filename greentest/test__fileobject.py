import os
import sys
import greentest
from gevent.fileobject import SocketAdapter, FileObjectPosix


class Test(greentest.TestCase):

    def test_del(self):
        r, w = os.pipe()
        s = SocketAdapter(w)
        s.sendall('x')
        del s
        self.assertEqual(FileObjectPosix(r).read(), 'x')


if __name__ == '__main__':
    greentest.main()
