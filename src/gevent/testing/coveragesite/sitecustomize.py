# When testrunner.py is invoked with --coverage, it puts this first
# on the path as per https://coverage.readthedocs.io/en/coverage-4.0b3/subprocess.html.
# Note that this disables other sitecustomize.py files.
import coverage
import coverage.exceptions
try:
    coverage.process_startup()
except (coverage.CoverageException,
        # As of Coverage 7, the ConfigError seems to be the one raised.
        # Not sure when that changed, it used to be CoverageException. Go
        # ahead and keep both for safety.
        coverage.exceptions.ConfigError) as e:

    if str(e) in (
        "Can't support concurrency=greenlet with PyTracer, only threads are supported",
    ):
        pass
    elif str(e) in (
        # We get this one for the stdlib test_interpreters: greenlet up through at least
        # 3.2.0 produces "ImportError: module greenlet._greenlet does not support loading
        # in subinterpreters". Now, this is a fairly broad brush with which to try to
        # catch that specific case, so we fallback and look for that import error
        # as well to make it more specific to exactly this case.
        "Couldn't trace with concurrency=greenlet, the module isn't installed.",
    ):
        ignore = False
        try:
            __import__('greenlet')
        except ImportError as ie:
            if str(ie) in (
                "module greenlet._greenlet does not support loading in subinterpreters",
            ):
                ignore = True
        if not ignore:
            raise

    else:
        import traceback
        traceback.print_exc()
        raise
except:
    import traceback
    traceback.print_exc()
    raise
