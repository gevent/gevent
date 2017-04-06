# This file is renamed to "Makefile.ext" in release tarballs so that setup.py won't try to
# run it.  If you want setup.py to run "make" automatically, rename it back to "Makefile".

# The pyvenv multiple runtime support is based on https://github.com/DRMacIver/hypothesis/blob/master/Makefile

PYTHON?=python${TRAVIS_PYTHON_VERSION}
CYTHON?=cython



export PATH:=$(BUILD_RUNTIMES)/snakepit:$(TOOLS):$(PATH)
export LC_ALL=C.UTF-8


all: src/gevent/libev/gevent.corecext.c src/gevent/gevent.ares.c src/gevent/gevent._semaphore.c

src/gevent/libev/gevent.corecext.c: src/gevent/libev/corecext.ppyx src/gevent/libev/libev.pxd util/cythonpp.py
	$(PYTHON) util/cythonpp.py -o gevent.corecext.c --module-name gevent.libev.corecext.pyx src/gevent/libev/corecext.ppyx
	echo '#include "callbacks.c"' >> gevent.corecext.c
	mv gevent.corecext.* src/gevent/libev/

src/gevent/gevent.ares.c: src/gevent/ares.pyx src/gevent/*.pxd
	$(CYTHON) -o gevent.ares.c src/gevent/ares.pyx
	mv gevent.ares.* src/gevent/

src/gevent/gevent._semaphore.c: src/gevent/_semaphore.py src/gevent/_semaphore.pxd
# On PyPy, if we wanted to use Cython to compile _semaphore.py, we'd
# need to have _semaphore named as a .pyx file so it doesn't get
# loaded in preference to the .so. (We want to keep the definitions
# separate in a .pxd file for ease of reading, and that only works
# with .py files, so we'd have to copy them back and forth.)
#	cp src/gevent/_semaphore.pyx src/gevent/_semaphore.py
	$(CYTHON) -o gevent._semaphore.c src/gevent/_semaphore.py
	mv gevent._semaphore.* src/gevent/
#	rm src/gevent/_semaphore.py

clean:
	rm -f corecext.pyx src/gevent/libev/corecext.pyx
	rm -f gevent.corecext.c gevent.corecext.h src/gevent/libev/gevent.corecext.c src/gevent/libev/gevent.corecext.h
	rm -f gevent.ares.c gevent.ares.h src/gevent/gevent.ares.c src/gevent/gevent.ares.h
	rm -f gevent._semaphore.c gevent._semaphore.h src/gevent/gevent._semaphore.c src/gevent/gevent._semaphore.h
	rm -f src/gevent/*.so src/gevent/libev/*.so
	rm -rf src/gevent/libev/*.o src/gevent/*.o
	rm -rf src/gevent/__pycache__ src/greentest/__pycache__ src/gevent/libev/__pycache__
	rm -rf src/gevent/*.pyc src/greentest/*.pyc src/gevent/libev/*.pyc
	rm -rf src/greentest/htmlcov src/greentest/.coverage
	rm -rf build

distclean: clean
	rm -rf dist
	rm -rf deps/libev/config.h deps/libev/config.log deps/libev/config.status deps/libev/.deps deps/libev/.libs
	rm -rf deps/c-ares/config.h deps/c-ares/config.log deps/c-ares/config.status deps/c-ares/.deps deps/c-ares/.libs

doc:
	cd doc && PYTHONPATH=.. make html

whitespace:
	! find . -not -path "*.pem" -not -path "./.eggs/*" -not -path "./src/greentest/htmlcov/*" -not -path "./src/greentest/.coverage.*" -not -path "./.tox/*" -not -path "*/__pycache__/*" -not -path "*.so" -not -path "*.pyc" -not -path "./.git/*" -not -path "./build/*"  -not -path "./src/gevent/libev/*" -not -path "./src/gevent.egg-info/*" -not -path "./dist/*" -not -path "./.DS_Store" -not -path "./deps/*" -not -path "./src/gevent/gevent.*.[ch]" -not -path "./src/gevent/corecext.pyx" -not -path "./doc/_build/*" -not -path "./doc/mytheme/static/*" -type f | xargs egrep -l " $$"

prospector:
	which prospector
	which pylint
# debugging
#	pylint --rcfile=.pylintrc --init-hook="import sys, code; sys.excepthook = lambda exc, exc_type, tb: print(tb.tb_next.tb_next.tb_next.tb_next.tb_next.tb_next.tb_next.tb_next.tb_next.tb_next.tb_frame.f_locals['self'])" gevent src/greentest/* || true
	${PYTHON} scripts/gprospector.py -X

lint: whitespace prospector

test_prelim:
	which ${PYTHON}
	${PYTHON} --version
	${PYTHON} -c 'import greenlet; print(greenlet, greenlet.__version__)'
	${PYTHON} -c 'import gevent.core; print(gevent.core.loop)'
	make bench

toxtest: test_prelim
	cd src/greentest && GEVENT_RESOLVER=thread ${PYTHON} testrunner.py --config known_failures.py --quiet

fulltoxtest: test_prelim
	cd src/greentest && GEVENT_RESOLVER=thread ${PYTHON} testrunner.py --config known_failures.py --quiet
	cd src/greentest && GEVENT_RESOLVER=ares GEVENTARES_SERVERS=8.8.8.8 ${PYTHON} testrunner.py --config known_failures.py --ignore tests_that_dont_use_resolver.txt --quiet
	cd src/greentest && GEVENT_FILE=thread ${PYTHON} testrunner.py --config known_failures.py `grep -l subprocess test_*.py` --quiet

leaktest:
	GEVENTSETUP_EV_VERIFY=3 GEVENTTEST_LEAKCHECK=1 make fulltoxtest

bench:
	${PYTHON} src/greentest/bench_sendall.py


travis_test_linters:
	make lint
	GEVENTTEST_COVERAGE=1 make leaktest
# because we set parallel=true, each run produces new and different coverage files; they all need
# to be combined
	coverage combine . src/greentest/

	coveralls --rcfile=src/greentest/.coveragerc


.PHONY: clean all doc prospector whitespace lint travistest travis

# Managing runtimes

BUILD_RUNTIMES?=$(PWD)/.runtimes

PY278=$(BUILD_RUNTIMES)/snakepit/python2.7.8
PY27=$(BUILD_RUNTIMES)/snakepit/python2.7.13
PY34=$(BUILD_RUNTIMES)/snakepit/python3.4.5
PY35=$(BUILD_RUNTIMES)/snakepit/python3.5.3
PY36=$(BUILD_RUNTIMES)/snakepit/python3.6.0
PYPY=$(BUILD_RUNTIMES)/snakepit/pypy571
PYPY3=$(BUILD_RUNTIMES)/snakepit/pypy3.5_571

TOOLS=$(BUILD_RUNTIMES)/tools

TOX=$(TOOLS)/tox

TOOL_VIRTUALENV=$(BUILD_RUNTIMES)/virtualenvs/tools
ISORT_VIRTUALENV=$(BUILD_RUNTIMES)/virtualenvs/isort
TOOL_PYTHON=$(TOOL_VIRTUALENV)/bin/python
TOOL_PIP=$(TOOL_VIRTUALENV)/bin/pip
TOOL_INSTALL=$(TOOL_PIP) install --upgrade

$(PY278):
	scripts/install.sh 2.7.8

$(PY27):
	scripts/install.sh 2.7

$(PY34):
	scripts/install.sh 3.4

$(PY35):
	scripts/install.sh 3.5

$(PY36):
	scripts/install.sh 3.6

$(PYPY):
	scripts/install.sh pypy

$(PYPY3):
	scripts/install.sh pypy3

PIP?=$(BUILD_RUNTIMES)/versions/$(PYTHON)/bin/pip

develop:
	ls -l $(BUILD_RUNTIMES)/snakepit/
	echo pip is at `which $(PIP)`
	echo python is at `which $(PYTHON)`
# First install a newer pip so that it can use the wheel cache
# (only needed until travis upgrades pip to 7.x; note that the 3.5
# environment uses pip 7.1 by default)
	${PIP} install -U pip
# Then start installing our deps so they can be cached. Note that use of --build-options / --global-options / --install-options
# disables the cache.
# We need wheel>=0.26 on Python 3.5. See previous revisions.
	${PIP} install -U -r dev-requirements.txt

lint-py27: $(PY27)
	PYTHON=python2.7.13 PATH=$(BUILD_RUNTIMES)/versions/python2.7.13/bin:$(PATH) make develop travis_test_linters

test-py27: $(PY27)
	PYTHON=python2.7.13 PATH=$(BUILD_RUNTIMES)/versions/python2.7.13/bin:$(PATH) make develop fulltoxtest

test-py278: $(PY278)
	ls $(BUILD_RUNTIMES)/versions/python2.7.8/bin/
	PYTHON=python2.7.8 PATH=$(BUILD_RUNTIMES)/versions/python2.7.8/bin:$(PATH) make develop toxtest

test-py34: $(PY34)
	PYTHON=python3.4.5 PIP=pip PATH=$(BUILD_RUNTIMES)/versions/python3.4.5/bin:$(PATH) make develop toxtest

test-py35: $(PY35)
	PYTHON=python3.5.3 PIP=pip PATH=$(BUILD_RUNTIMES)/versions/python3.5.3/bin:$(PATH) make develop fulltoxtest

test-py36: $(PY36)
	PYTHON=python3.6.0 PIP=pip PATH=$(BUILD_RUNTIMES)/versions/python3.6.0/bin:$(PATH) make develop toxtest

test-pypy: $(PYPY)
	PYTHON=$(PYPY) PIP=pip PATH=$(BUILD_RUNTIMES)/versions/pypy571/bin:$(PATH) make develop toxtest

test-pypy3: $(PYPY3)
	PYTHON=$(PYPY3) PIP=pip PATH=$(BUILD_RUNTIMES)/versions/pypy3.5_571/bin:$(PATH) make develop toxtest

test-py27-cffi: $(PY27)
	GEVENT_CORE_CFFI_ONLY=1 PYTHON=python2.7.13 PATH=$(BUILD_RUNTIMES)/versions/python2.7.13/bin:$(PATH) make develop toxtest

test-py27-noembed: $(PY27)
	cd deps/libev && ./configure --disable-dependency-tracking && make
	cd deps/c-ares && ./configure --disable-dependency-tracking && make
	CPPFLAGS="-Ideps/libev -Ideps/c-ares" LDFLAGS="-Ldeps/libev/.libs -Ldeps/c-ares/.libs" LD_LIBRARY_PATH="$(PWD)/deps/libev/.libs:$(PWD)/deps/c-ares/.libs" EMBED=0 GEVENT_CORE_CEXT_ONLY=1 PYTHON=python2.7.13 PATH=$(BUILD_RUNTIMES)/versions/python2.7.13/bin:$(PATH) make develop toxtest
