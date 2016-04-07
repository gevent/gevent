import sys

PY3 = sys.version_info[0] >= 3

if PY3:
    advance_iterator = next
else:
    def advance_iterator(it):
        return it.next()

if PY3:
    import builtins
    exec_ = getattr(builtins, "exec")

    def reraise(tp, value, tb=None):
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value

    xrange = range
    string_types = str,
    text_type = str

else:
    def exec_(code, globs=None, locs=None):
        """Execute code in a namespace."""
        if globs is None:
            frame = sys._getframe(1)
            globs = frame.f_globals
            if locs is None:
                locs = frame.f_locals
            del frame
        elif locs is None:
            locs = globs
        exec("""exec code in globs, locs""")

    import __builtin__ as builtins
    xrange = builtins.xrange
    string_types = builtins.basestring,
    text_type = builtins.unicode
