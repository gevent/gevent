"""
Tests for running ``gevent.monkey`` as a module to launch a
patched script.

Uses files in the ``monkey_package/`` directory.
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division


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

    def _run(self, script, module=False):
        env = os.environ.copy()
        env['PYTHONWARNINGS'] = 'ignore'
        args = [sys.executable, '-m', 'gevent.monkey']
        if module:
            args.append('--module')
        args += [script, 'patched']
        p = Popen(args, stdout=PIPE, stderr=PIPE, env=env)
        monkey_out, monkey_err = p.communicate()
        self.assertEqual(0, p.returncode, (monkey_out, monkey_err))

        if module:
            args = [sys.executable, "-m", script, 'stdlib']
        else:
            args = [sys.executable, script, 'stdlib']
        p = Popen(args, stdout=PIPE, stderr=PIPE)

        std_out, std_err = p.communicate()
        self.assertEqual(0, p.returncode, (std_out, std_err))

        monkey_out_lines = monkey_out.decode("utf-8").splitlines()
        std_out_lines = std_out.decode('utf-8').splitlines()
        self.assertEqual(monkey_out_lines, std_out_lines)
        self.assertEqual(monkey_err, std_err)

        return monkey_out_lines, monkey_err

    def test_run_simple(self):
        self._run(os.path.join('monkey_package', 'script.py'))

    def _run_package(self, module):
        lines, _ = self._run('monkey_package', module=module)

        self.assertTrue(lines[0].endswith('__main__.py'), lines[0])
        self.assertEqual(lines[1], '__main__')

    def test_run_package(self):
        # Run a __main__ inside a package, even without specifying -m
        self._run_package(module=False)

    def test_run_module(self):
        # Run a __main__ inside a package, when specifying -m
        self._run_package(module=True)

    def test_issue_302(self):
        lines, _ = self._run(os.path.join('monkey_package', 'issue302monkey.py'))

        self.assertEqual(lines[0], 'True')
        lines[1] = lines[1].replace('\\', '/') # windows path
        self.assertEqual(lines[1], 'monkey_package/issue302monkey.py')
        self.assertEqual(lines[2], 'True', lines)

    def test_threadpool_in_patched_after_patch(self):
        # Issue 1484
        # If we don't have this correct, then we get exceptions
        out, err = self._run(os.path.join('monkey_package', 'threadpool_monkey_patches.py'))
        self.assertEqual(out, ['False', '2'])
        self.assertEqual(err, b'')

    def test_threadpool_in_patched_after_patch_module(self):
        # Issue 1484
        # If we don't have this correct, then we get exceptions
        out, err = self._run('monkey_package.threadpool_monkey_patches', module=True)
        self.assertEqual(out, ['False', '2'])
        self.assertEqual(err, b'')

    def test_threadpool_not_patched_after_patch_module(self):
        # Issue 1484
        # If we don't have this correct, then we get exceptions
        out, err = self._run('monkey_package.threadpool_no_monkey', module=True)
        self.assertEqual(out, ['False', 'False', '2'])
        self.assertEqual(err, b'')

if __name__ == '__main__':
    unittest.main()
