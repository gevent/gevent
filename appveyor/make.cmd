IF "%PYTHON_EXE%" == "python" (
    %PYEXE% util/cythonpp.py -o gevent.corecext.c gevent/corecext.ppyx
	type gevent\\callbacks.c >> gevent.corecext.c
    move gevent.corecext.* gevent
)
cython -o gevent.ares.c gevent/ares.pyx
move gevent.ares.* gevent
move gevent\\_semaphore.pyx gevent\\_semaphore.py
cython -o gevent._semaphore.c gevent/_semaphore.py
move gevent._semaphore.* gevent
del gevent\\_semaphore.py
cython -o gevent._util.c gevent/_util.pyx
move gevent._util.* gevent
