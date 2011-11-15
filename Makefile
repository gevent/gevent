# This file is renamed to "Makefile.ext" in release tarballs so that setup.py won't try to
# run it.  If you want setup.py to run "make" automatically, rename it back to "Makefile".

PYTHON ?= python

all: gevent/gevent.core.c gevent/gevent.ares.c

gevent/gevent.core.c: gevent/core.ppyx gevent/libev.pxd util/cythonpp.py
	$(PYTHON) util/cythonpp.py -o gevent.core.c gevent/core.ppyx
	echo                          >> gevent.core.c
	echo '#include "callbacks.c"' >> gevent.core.c
	mv gevent.core.* gevent/

gevent/gevent.ares.c: gevent/*.pyx gevent/*.pxd
	cython -o gevent.ares.c gevent/ares.pyx
	mv gevent.ares.* gevent/

clean:
	rm -f gevent.core.c gevent.core.h core.pyx gevent/gevent.core.c gevent/gevent.core.h gevent/core.pyx
	rm -f gevent.ares.c gevent.ares.h gevent/gevent.ares.c gevent/gevent.ares.h

.PHONY: clean all
