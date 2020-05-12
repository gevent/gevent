Waiters on Event and Semaphore objects that call ``wait()`` or
``acquire()``, respectively, that find the Event already set, or the
Semaphore available, no longer "cut in line" and run before any
previously scheduled greenlets. They now run in the order in which
they arrived, just as waiters that had to block in those methods do.
