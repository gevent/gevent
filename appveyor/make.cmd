IF "%PYTHON_EXE%" == "python" (
    cython -o gevent.corecext.c src\gevent\libev\corecext.ppyx
	type src\gevent\libev\callbacks.c >> gevent.corecext.c
    move gevent.corecext.* src\gevent\libev
)
cython -o gevent.ares.c src\gevent\ares.pyx
move gevent.ares.* src\gevent
cython -o gevent._semaphore.c src\gevent\_semaphore.py
move gevent._semaphore.* src\gevent
cython -o gevent._local.c src\gevent\local.py
move gevent._local.c src\gevent
