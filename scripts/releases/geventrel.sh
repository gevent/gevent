#!/opt/local/bin/bash
#
# Quick hack script to build a single gevent release in a virtual env. Takes one
# argument, the path to python to use.
# Has hardcoded paths, probably only works on my (JAM) machine.

set -e
export WORKON_HOME=$HOME/Projects/VirtualEnvs
export VIRTUALENVWRAPPER_LOG_DIR=~/.virtualenvs
source `which virtualenvwrapper.sh`

# Make sure there are no -march flags set
# https://github.com/gevent/gevent/issues/791
unset CFLAGS
unset CXXFLAGS
unset CPPFLAGS

cd /tmp/gevent
virtualenv -p $1 `basename $1`
cd `basename $1`
echo "Made tmpenv"
echo `pwd`
source bin/activate
git clone https://github.com/gevent/gevent
cd gevent
pip install -U pip
pip install -U setuptools cython greenlet cffi
pip install -U wheel
python ./setup.py sdist bdist_wheel
cp dist/*whl /tmp/gevent/
