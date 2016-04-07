# When testrunner.py is invoked with --coverage, it puts this first
# on the path as per http://coverage.readthedocs.org/en/coverage-4.0b3/subprocess.html.
# Note that this disables other sitecustomize.py files.
import coverage
coverage.process_startup()
