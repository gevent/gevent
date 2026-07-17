"""
The patched ``threading._shutdown`` must run the ``_register_atexit`` hooks
before it joins non-daemon threads, the way the native one does: a thread may
be waiting on a hook.

Nothing here asserts that; a regression hangs the interpreter at exit, which
the test runner catches at its timeout.
"""
from gevent import monkey; monkey.patch_all() # pragma: testrunner-no-monkey-combine

import threading
from concurrent.futures import ThreadPoolExecutor

from gevent import testing as greentest

executor = None


class Test(greentest.TestCase):

    @greentest.ignores_leakcheck # the thread and the hook only go away at exit
    def test_thread_waiting_on_hook(self):
        done = threading.Event()
        threading._register_atexit(done.set)
        threading.Thread(target=done.wait).start()

    def test_thread_pool_executor(self):
        # How the bug reached real code: concurrent.futures registers
        # _python_exit (bpo-39812), the only thing that stops a pool's
        # non-daemon workers. The executor has to stay alive; once collected,
        # its weakref callback stops the workers and the hang never happens.
        global executor
        executor = ThreadPoolExecutor(max_workers=2)
        self.assertEqual(list(executor.map(int, ('1', '2'))), [1, 2])


if __name__ == '__main__':
    greentest.main()
