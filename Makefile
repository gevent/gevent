# This file is renamed to "Makefile.ext" in release tarballs so that setup.py won't try to
# run it.  If you want setup.py to run "make" automatically, rename it back to "Makefile".

PYTHON ?= python
CYTHON ?= cython

all: gevent/gevent.core.c gevent/gevent.ares.c gevent/gevent._semaphore.c gevent/gevent._util.c

gevent/gevent.core.c: gevent/core.ppyx gevent/libev.pxd
	$(PYTHON) util/cythonpp.py -o gevent.core.c gevent/core.ppyx
	echo                          >> gevent.core.c
	echo '#include "callbacks.c"' >> gevent.core.c
	mv gevent.core.* gevent/

gevent/gevent.ares.c: gevent/ares.pyx gevent/core.pyx gevent/*.pxd
	$(CYTHON) -o gevent.ares.c gevent/ares.pyx
	mv gevent.ares.* gevent/

gevent/gevent._semaphore.c: gevent/_semaphore.pyx
	$(CYTHON) -o gevent._semaphore.c gevent/_semaphore.pyx
	mv gevent._semaphore.* gevent/

gevent/gevent._util.c: gevent/_util.pyx
	$(CYTHON) -o gevent._util.c gevent/_util.pyx
	mv gevent._util.* gevent/

clean:
	rm -f gevent.core.c gevent.core.h core.pyx gevent/gevent.core.c gevent/gevent.core.h gevent/core.pyx
	rm -f gevent.ares.c gevent.ares.h gevent/gevent.ares.c gevent/gevent.ares.h
	rm -f gevent._semaphore.c gevent._semaphore.h gevent/gevent._semaphore.c gevent/gevent._semaphore.h
	rm -f gevent._util.c gevent._util.h gevent/gevent._util.c gevent/gevent._util.h

.PHONY: clean all
