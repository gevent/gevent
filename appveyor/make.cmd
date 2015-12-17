IF "%PYTHON_EXE%" == "python" (
    %PYEXE% util/cythonpp.py -o gevent.corecext.c gevent/corecext.ppyx
	type gevent\\callbacks.c >> gevent.corecext.c
    move gevent.corecext.* gevent
)
cython -o gevent.ares.c gevent/ares.pyx
move gevent.ares.* gevent
cython -o gevent._semaphore.c gevent/_semaphore.py
move gevent._semaphore.* gevent
