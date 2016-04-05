IF "%PYTHON_EXE%" == "python" (
    %PYEXE% util\cythonpp.py -o gevent.corecext.c --module-name gevent.libev.corecext.pyx src\gevent\libev\corecext.ppyx
	type src\gevent\libev\callbacks.c >> gevent.corecext.c
    move gevent.corecext.* src\gevent\libev
)
cython -o gevent.ares.c src\gevent\ares.pyx
move gevent.ares.* src\gevent
cython -o gevent._semaphore.c src\gevent\_semaphore.py
move gevent._semaphore.* src\gevent
