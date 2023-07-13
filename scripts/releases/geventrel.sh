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

# If we're building on 10.12, we have to exclude clock_gettime
# because it's not available on earlier releases and leads to
# segfaults because the symbol clock_gettime is NULL.
# See https://github.com/gevent/gevent/issues/916
#export CPPFLAGS="-D_DARWIN_FEATURE_CLOCK_GETTIME=0"
export ARCHFLAGS="-arch arm64 -arch x86_64"

BASE=`pwd`/../../
BASE=`greadlink -f $BASE`


cd /tmp/gevent
virtualenv -p $1 `basename $1`
cd `basename $1`
echo "Made tmpenv"
echo `pwd`
source bin/activate
echo cloning $BASE
git clone $BASE gevent
cd ./gevent
pip install -U pip
pip wheel . -w dist
cp dist/gevent*whl /tmp/gevent/
