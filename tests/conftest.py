import sys, os

# Ensure project root (parent of tests directory) is on sys.path for imports when
# test execution occurs in environments that don't automatically include it.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
