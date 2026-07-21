Fix a hang at interpreter exit, on Python 3.13 and above, when a non-daemon
thread is waiting on a ``threading._register_atexit`` hook. The patched
``threading._shutdown`` joined those threads before running the hooks, the
reverse of the native order. This hung any program holding a live
:class:`concurrent.futures.ThreadPoolExecutor`, whose non-daemon workers stop
only when its ``_python_exit`` hook runs.
