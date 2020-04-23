#!/opt/local/bin/bash

# Quick hack script to create many gevent releases.
# Contains hardcoded paths. Probably only works on my (JAM) machine
# (OS X 10.11)

mkdir /tmp/gevent/


# 2.7 is a python.org build, builds a 10_6_intel wheel
./geventrel.sh /usr/local/bin/python2.7 &

# 3.5 is a python.org build, builds a 10_6_intel wheel
./geventrel.sh /usr/local/bin/python3.5 &

# 3.6 is a python.org build, builds a 10_6_intel wheel
./geventrel.sh /usr/local/bin/python3.6 &

# 3.7 is a python.org build, builds a 10_6_intel wheel
./geventrel.sh /usr/local/bin/python3.7 &
./geventrel.sh /usr/local/bin/python3.8 &


# PyPy 4.0
./geventrel.sh `which pypy` &

wait
