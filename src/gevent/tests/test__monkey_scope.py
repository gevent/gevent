import os
import os.path
import sys

import unittest

from subprocess import Popen
from subprocess import PIPE

class TestRun(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.cwd = os.getcwd()
        os.chdir(os.path.dirname(__file__))

    def tearDown(self):
        os.chdir(self.cwd)

    def _run(self, script):
        env = os.environ.copy()
        env['PYTHONWARNINGS'] = 'ignore'
        args = [sys.executable, '-m', 'gevent.monkey', script, 'patched']
        p = Popen(args, stdout=PIPE, stderr=PIPE, env=env)
        gout, gerr = p.communicate()
        self.assertEqual(0, p.returncode, (gout, gerr))

        args = [sys.executable, script, 'stdlib']
        p = Popen(args, stdout=PIPE, stderr=PIPE)

        pout, perr = p.communicate()
        self.assertEqual(0, p.returncode, (pout, perr))

        glines = gout.decode("utf-8").splitlines()
        plines = pout.decode('utf-8').splitlines()
        self.assertEqual(glines, plines)
        self.assertEqual(gerr, perr)

        return glines, gerr

    def test_run_simple(self):
        self._run(os.path.join('monkey_package', 'script.py'))

    def test_run_package(self):
        # Run a __main__ inside a package.
        lines, _ = self._run('monkey_package')

        self.assertTrue(lines[0].endswith('__main__.py'), lines[0])
        self.assertEqual(lines[1], '__main__')

    def test_issue_302(self):
        lines, _ = self._run(os.path.join('monkey_package', 'issue302monkey.py'))

        self.assertEqual(lines[0], 'True')
        lines[1] = lines[1].replace('\\', '/') # windows path
        self.assertEqual(lines[1], 'monkey_package/issue302monkey.py')
        self.assertEqual(lines[2], 'True', lines)


if __name__ == '__main__':
    unittest.main()
