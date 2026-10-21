# pytest configuration for the skencil-tk test suite.
#
# Imports testsupport early so that the build tree is on sys.path before
# any test module imports Sketch, and so that `import testsupport' works
# from the test modules regardless of the pytest rootdir.

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testsupport  # noqa: E402

testsupport.sketch()  # bootstrap the build tree before collection
