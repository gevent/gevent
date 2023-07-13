#!/opt/local/bin/bash

# Quick hack script to create many gevent releases.
# Contains hardcoded paths. Probably only works on my (JAM) machine
# (OS X 10.11)

mkdir /tmp/gevent/


./geventrel.sh /usr/local/bin/python3.8
./geventrel.sh /usr/local/bin/python3.9
./geventrel.sh /usr/local/bin/python3.10
./geventrel.sh /usr/local/bin/python3.11
./geventrel.sh /usr/local/bin/python3.12

wait
