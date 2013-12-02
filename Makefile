# This file is renamed to "Makefile.ext" in release tarballs so that setup.py won't try to
# run it.  If you want setup.py to run "make" automatically, rename it back to "Makefile".

PYTHON ?= python${PYTHONVER}
CYTHON ?= cython

all: gevent/gevent.core.c gevent/gevent.ares.c gevent/gevent._semaphore.c gevent/gevent._util.c

gevent/gevent.core.c: gevent/core.ppyx gevent/libev.pxd
	$(PYTHON) util/cythonpp.py -o gevent.core.c gevent/core.ppyx
	echo                          >> gevent.core.c
	echo '#include "callbacks.c"' >> gevent.core.c
	mv gevent.core.* gevent/

gevent/gevent.ares.c: gevent/ares.pyx gevent/*.pxd
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

doc:
	cd doc && PYTHONPATH=.. make html

whitespace:
	! find . -not -path "./.git/*" -not -path "./build/*" -not -path "./libev/*" -not -path "./c-ares/*" -not -path "./doc/_build/*" -type f | xargs egrep -l " $$"

pep8:
	pep8 .

pyflakes:
	util/pyflakes.py

lint: whitespace pep8 pyflakes

travistest:
	which ${PYTHON}
	${PYTHON} --version

	cd greenlet-* && ${PYTHON} setup.py install -q
	${PYTHON} -c 'import greenlet; print(greenlet, greenlet.__version__)'

	${PYTHON} setup.py install

	cd greentest && GEVENT_RESOLVER=thread ${PYTHON} testrunner.py --expected ../known_failures.txt
	cd greentest && GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 ${PYTHON} testrunner.py --expected ../known_failures.txt --ignore tests_that_dont_use_resolver.txt
	# --ignore option does not work as expected XXX
	cd greentest && GEVENT_FILE=thread ${PYTHON} testrunner.py --expected ../known_failures.txt --ignore tests_that_dont_use_subprocess.txt

travis:
	make whitespace

	pip install -q pep8
	make pep8

	pip install -q pyflakes
	make pyflakes

	sudo add-apt-repository -y ppa:chris-lea/cython
	sudo apt-get -qq -y update
	sudo apt-get -qq -y install cython
	cython --version

	pip install -q --download . greenlet
	unzip -q greenlet-*.zip

	ack -w subprocess greentest/ -l -v | python -c 'import sys; print("\n".join(line.split("/")[-1].strip() for line in sys.stdin))' > greentest/tests_that_dont_use_subprocess.txt

	make travistest

	apt-get install ${PYTHON}-dbg

	PYTHON=${PYTHON}-dbg GEVENTSETUP_EV_VERIFY=3 make travistest


.PHONY: clean all doc pep8 whitespace pyflakes lint travistest travis
