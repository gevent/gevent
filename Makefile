# This file is renamed to "Makefile.ext" in release tarballs so that setup.py won't try to
# run it.  If you want setup.py to run "make" automatically, rename it back to "Makefile".

PYTHON ?= python${TRAVIS_PYTHON_VERSION}
CYTHON ?= cython

all: gevent/gevent.corecext.c gevent/gevent.ares.c gevent/gevent._semaphore.c gevent/gevent._util.c

gevent/gevent.corecext.c: gevent/core.ppyx gevent/libev.pxd
	$(PYTHON) util/cythonpp.py -o gevent.corecext.c gevent/core.ppyx
	echo '#include "callbacks.c"' >> gevent.corecext.c
	mv gevent.corecext.* gevent/

gevent/gevent.ares.c: gevent/ares.pyx gevent/*.pxd
	$(CYTHON) -o gevent.ares.c gevent/ares.pyx
	mv gevent.ares.* gevent/

gevent/gevent._semaphore.c: gevent/_semaphore.pyx gevent/_semaphore.pxd
# For PyPy, we need to have _semaphore named as a .pyx file so it doesn't
# get loaded in preference to the .so. But we want to keep the definitions
# separate in a .pxd file for ease of reading, and that only works
# with .py files.
	cp gevent/_semaphore.pyx gevent/_semaphore.py
	$(CYTHON) -o gevent._semaphore.c gevent/_semaphore.py
	mv gevent._semaphore.* gevent/
	rm gevent/_semaphore.py

gevent/gevent._util.c: gevent/_util.pyx
	$(CYTHON) -o gevent._util.c gevent/_util.pyx
	mv gevent._util.* gevent/

clean:
	rm -f gevent.core.c gevent.core.h core.pyx gevent/gevent.core.c gevent/gevent.core.h gevent/core.pyx
	rm -f gevent.corecext.c gevent.corecext.h gevent/gevent.corecext.c gevent/gevent.corecext.h
	rm -f gevent.ares.c gevent.ares.h gevent/gevent.ares.c gevent/gevent.ares.h
	rm -f gevent._semaphore.c gevent._semaphore.h gevent/gevent._semaphore.c gevent/gevent._semaphore.h
	rm -f gevent._util.c gevent._util.h gevent/gevent._util.c gevent/gevent._util.h

doc:
	cd doc && PYTHONPATH=.. make html

whitespace:
	! find . -not -path "./.eggs/*" -not -path "./greentest/htmlcov/*" -not -path "./greentest/.coverage.*" -not -path "./.tox/*" -not -path "*/__pycache__/*" -not -path "*.so" -not -path "*.pyc" -not -path "./.git/*" -not -path "./build/*" -not -path "./libev/*" -not -path "./gevent/libev/*" -not -path "./gevent.egg-info/*" -not -path "./dist/*" -not -path "./.DS_Store" -not -path "./c-ares/*" -not -path "./gevent/gevent.*.[ch]" -not -path "./gevent/core.pyx" -not -path "./doc/_build/*" -not -path "./doc/mytheme/static/*" -type f | xargs egrep -l " $$"

pep8:
	${PYTHON} `which pep8` .

pyflakes:
	${PYTHON} util/pyflakes.py

lint: whitespace pyflakes pep8

travistest:
	which ${PYTHON}
	${PYTHON} --version

	${PYTHON} -c 'import greenlet; print(greenlet, greenlet.__version__)'

# develop, not install, so that coverage doesn't think it's part of the stdlib
	${PYTHON} setup.py develop
	make bench

	cd greentest && GEVENT_RESOLVER=thread ${PYTHON} testrunner.py --config ../known_failures.py
	cd greentest && GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 ${PYTHON} testrunner.py --config ../known_failures.py --ignore tests_that_dont_use_resolver.txt
	cd greentest && GEVENT_FILE=thread ${PYTHON} testrunner.py --config ../known_failures.py `grep -l subprocess test_*.py`
# because we set parallel=true, each run produces new and different coverage files; they all need
# to be combined
	coverage combine . greentest/

toxtest:
	cd greentest && GEVENT_RESOLVER=thread python testrunner.py --config ../known_failures.py

fulltoxtest:
	cd greentest && GEVENT_RESOLVER=thread python testrunner.py --config ../known_failures.py
	cd greentest && GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 python testrunner.py --config ../known_failures.py --ignore tests_that_dont_use_resolver.txt
	cd greentest && GEVENT_FILE=thread python testrunner.py --config ../known_failures.py `grep -l subprocess test_*.py`

leaktest:
	GEVENTSETUP_EV_VERIFY=3 GEVENTTEST_LEAKCHECK=1 make travistest

bench:
	${PYTHON} greentest/bench_sendall.py

travis_pypy:
	which ${PYTHON}
	${PYTHON} --version
	${PYTHON} setup.py install
	make bench
	cd greentest && ${PYTHON} testrunner.py --config ../known_failures.py

travis_cpython:
	pip install cython greenlet

	make travistest

travis_test_linters:
	make lint
	GEVENTTEST_COVERAGE=1 make leaktest
	coveralls --rcfile=greentest/.coveragerc


.PHONY: clean all doc pep8 whitespace pyflakes lint travistest travis
