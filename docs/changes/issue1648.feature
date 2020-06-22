The embedded libev is now asked to detect the availability of
``clock_gettime`` and use the realtime and/or monotonic clocks, if
they are available.

On Linux, this can reduce the number of system calls libev makes.
Originally provided by Josh Snyder.
