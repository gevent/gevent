IF "%PYTHON_EXE%" == "python" (
    %PYEXE% util\cythonpp.py -o gevent.corecext.c src\gevent\corecext.ppyx
	type src\gevent\callbacks.c >> gevent.corecext.c
    move gevent.corecext.* src\gevent
)
cython -o gevent.ares.c src\gevent\ares.pyx
move gevent.ares.* src\gevent
cython -o gevent._semaphore.c src\gevent\_semaphore.py
move gevent._semaphore.* src\gevent
