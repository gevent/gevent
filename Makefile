# This file is renamed to "Makefile.ext" in release tarballs so that setup.py won't try to
# run it.  If you want setup.py to run "make" automatically, rename it back to "Makefile".

# The pyvenv multiple runtime support is based on https://github.com/DRMacIver/hypothesis/blob/master/Makefile

PYTHON?=python${TRAVIS_PYTHON_VERSION}
CYTHON?=cython



export PATH:=$(BUILD_RUNTIMES)/snakepit:$(TOOLS):$(PATH)
export LC_ALL=C.UTF-8


all: gevent/gevent.corecext.c gevent/gevent.ares.c gevent/gevent._semaphore.c

gevent/gevent.corecext.c: gevent/corecext.ppyx gevent/libev.pxd
	$(PYTHON) util/cythonpp.py -o gevent.corecext.c gevent/corecext.ppyx
	echo '#include "callbacks.c"' >> gevent.corecext.c
	mv gevent.corecext.* gevent/

gevent/gevent.ares.c: gevent/ares.pyx gevent/*.pxd
	$(CYTHON) -o gevent.ares.c gevent/ares.pyx
	mv gevent.ares.* gevent/

gevent/gevent._semaphore.c: gevent/_semaphore.py gevent/_semaphore.pxd
# On PyPy, if we wanted to use Cython to compile _semaphore.py, we'd
# need to have _semaphore named as a .pyx file so it doesn't get
# loaded in preference to the .so. (We want to keep the definitions
# separate in a .pxd file for ease of reading, and that only works
# with .py files, so we'd have to copy them back and forth.)
#	cp gevent/_semaphore.pyx gevent/_semaphore.py
	$(CYTHON) -o gevent._semaphore.c gevent/_semaphore.py
	mv gevent._semaphore.* gevent/
#	rm gevent/_semaphore.py

clean:
	rm -f corecext.pyx gevent/corecext.pyx
	rm -f gevent.corecext.c gevent.corecext.h gevent/gevent.corecext.c gevent/gevent.corecext.h
	rm -f gevent.ares.c gevent.ares.h gevent/gevent.ares.c gevent/gevent.ares.h
	rm -f gevent._semaphore.c gevent._semaphore.h gevent/gevent._semaphore.c gevent/gevent._semaphore.h

doc:
	cd doc && PYTHONPATH=.. make html

whitespace:
	! find . -not -path "*.pem" -not -path "./.eggs/*" -not -path "./greentest/htmlcov/*" -not -path "./greentest/.coverage.*" -not -path "./.tox/*" -not -path "*/__pycache__/*" -not -path "*.so" -not -path "*.pyc" -not -path "./.git/*" -not -path "./build/*" -not -path "./libev/*" -not -path "./gevent/libev/*" -not -path "./gevent.egg-info/*" -not -path "./dist/*" -not -path "./.DS_Store" -not -path "./c-ares/*" -not -path "./gevent/gevent.*.[ch]" -not -path "./gevent/corecext.pyx" -not -path "./doc/_build/*" -not -path "./doc/mytheme/static/*" -type f | xargs egrep -l " $$"

pep8:
	${PYTHON} `which pep8` .

pyflakes:
	${PYTHON} util/pyflakes.py

lint: whitespace pyflakes pep8

test_prelim:
	which ${PYTHON}
	${PYTHON} --version
	${PYTHON} -c 'import greenlet; print(greenlet, greenlet.__version__)'
	${PYTHON} -c 'import gevent.core; print(gevent.core.loop)'
	make bench

toxtest: test_prelim
	cd greentest && GEVENT_RESOLVER=thread python testrunner.py --config ../known_failures.py

fulltoxtest: test_prelim
	cd greentest && GEVENT_RESOLVER=thread ${PYTHON} testrunner.py --config ../known_failures.py
	cd greentest && GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 ${PYTHON} testrunner.py --config ../known_failures.py --ignore tests_that_dont_use_resolver.txt
	cd greentest && GEVENT_FILE=thread ${PYTHON} testrunner.py --config ../known_failures.py `grep -l subprocess test_*.py`

leaktest:
	GEVENTSETUP_EV_VERIFY=3 GEVENTTEST_LEAKCHECK=1 make fulltoxtest

bench:
	${PYTHON} greentest/bench_sendall.py


travis_test_linters:
	make lint
	GEVENTTEST_COVERAGE=1 make leaktest
# because we set parallel=true, each run produces new and different coverage files; they all need
# to be combined
	coverage combine . greentest/

	coveralls --rcfile=greentest/.coveragerc


.PHONY: clean all doc pep8 whitespace pyflakes lint travistest travis

# Managing runtimes

BUILD_RUNTIMES?=$(PWD)/.runtimes

PY26=$(BUILD_RUNTIMES)/snakepit/python2.6
PY27=$(BUILD_RUNTIMES)/snakepit/python2.7
PY33=$(BUILD_RUNTIMES)/snakepit/python3.3
PY34=$(BUILD_RUNTIMES)/snakepit/python3.4
PY35=$(BUILD_RUNTIMES)/snakepit/python3.5
PYPY=$(BUILD_RUNTIMES)/snakepit/pypy

TOOLS=$(BUILD_RUNTIMES)/tools

TOX=$(TOOLS)/tox

TOOL_VIRTUALENV=$(BUILD_RUNTIMES)/virtualenvs/tools
ISORT_VIRTUALENV=$(BUILD_RUNTIMES)/virtualenvs/isort
TOOL_PYTHON=$(TOOL_VIRTUALENV)/bin/python
TOOL_PIP=$(TOOL_VIRTUALENV)/bin/pip
TOOL_INSTALL=$(TOOL_PIP) install --upgrade

$(PY26):
	scripts/install.sh 2.6

$(PY27):
	scripts/install.sh 2.7

$(PY33):
	scripts/install.sh 3.3

$(PY34):
	scripts/install.sh 3.4

$(PY35):
	scripts/install.sh 3.5

$(PYPY):
	scripts/install.sh pypy

PIP?=$(BUILD_RUNTIMES)/versions/$(PYTHON)/bin/pip

develop:
	echo $(PIP) $(PYTHON)
# First install a newer pip so that it can use the wheel cache
# (only needed until travis upgrades pip to 7.x; note that the 3.5
# environment uses pip 7.1 by default)
	${PIP} install -U pip
# Then start installing our deps so they can be cached. Note that use of --build-options / --global-options / --install-options
# disables the cache.
# We need wheel>=0.26 on Python 3.5. See previous revisions.
	${PIP} install -U wheel
	${PIP} install -U tox cython cffi greenlet pep8 pyflakes "coverage>=4.0" "coveralls>=1.0"
	${PYTHON} setup.py develop

lint-py27: $(PY27)
	PYTHON=python2.7 PATH=$(BUILD_RUNTIMES)/versions/python2.7/bin:$(PATH) make develop travis_test_linters

test-py27: $(PY27)
	PYTHON=python2.7 PATH=$(BUILD_RUNTIMES)/versions/python2.7/bin:$(PATH) make develop fulltoxtest

test-py26: $(PY26)
	PYTHON=python2.6 PATH=$(BUILD_RUNTIMES)/versions/python2.6/bin:$(PATH) make develop fulltoxtest

test-py33: $(PY33)
	PYTHON=python3.3 PATH=$(BUILD_RUNTIMES)/versions/python3.3/bin:$(PATH) make develop fulltoxtest

test-py34: $(PY34)
	PYTHON=python3.4 PATH=$(BUILD_RUNTIMES)/versions/python3.4/bin:$(PATH) make develop fulltoxtest

test-py35: $(PY35)
	PYTHON=python3.5 PATH=$(BUILD_RUNTIMES)/versions/python3.5/bin:$(PATH) make develop fulltoxtest

test-pypy: $(PYPY)
	PYTHON=pypy PATH=$(BUILD_RUNTIMES)/versions/pypy/bin:$(PATH) make develop toxtest

test-py27-cffi: $(PY27)
	GEVENT_CORE_CFFI_ONLY=1 PYTHON=python2.7 PATH=$(BUILD_RUNTIMES)/versions/python2.7/bin:$(PATH) make develop toxtest
