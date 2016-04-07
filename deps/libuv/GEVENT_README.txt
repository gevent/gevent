We distribute libuv with configure already created, by autogen.sh
^^^
XXX: We would like to do that, but it is going to take some tinkering
to make that work.

Do not remove the test/ directory; the windows build depends on it
being in place. Sigh.
