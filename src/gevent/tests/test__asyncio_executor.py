# A ThreadPoolExecutor worker is a greenlet on the loop's OS thread.
# It must not observe that loop as "running", or CPython 3.13.12+ delivers
# the executor result with call_soon and the selector sleeps until a timer.
from gevent import monkey
monkey.patch_all()

import asyncio
import threading
import unittest


class TestAsyncioExecutorRunningLoop(unittest.TestCase):

    def test_worker_does_not_see_the_running_loop(self):
        seen = {}

        async def main():
            loop = asyncio.get_running_loop()
            seen['main'] = asyncio.events._get_running_loop()

            def work():
                seen['worker'] = asyncio.events._get_running_loop()
                seen['main_thread'] = (
                    threading.current_thread() is threading.main_thread()
                )
                return 'ok'

            result = await loop.run_in_executor(None, work)
            self.assertEqual(result, 'ok')
            self.assertIs(seen['main'], loop)

        asyncio.run(main())
        self.assertIsNone(seen['worker'])
        self.assertFalse(seen['main_thread'])


if __name__ == '__main__':
    unittest.main()
