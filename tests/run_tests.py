#!/usr/bin/env python3
"""Run all Python-based cross-platform memcached test suites.

Discovers and executes all test suites matching test_*.py in this directory.
"""

import os
import sys
import unittest


def main():
    """Discover and execute all memcached test modules.

    :return: None
    :rtype: None
    """
    test_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, test_dir)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=test_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
