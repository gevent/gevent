import sys
import os

if os.system("ack 'from test import (?!test_support)|from test\.(?!test_support)' 2.5 2.6 2.7") != 256:
    sys.exit('FAILED: Some tests in stdlib were not updated to not reference "test".')
