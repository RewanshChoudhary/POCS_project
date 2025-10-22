"""Test runner for all unit tests."""

import unittest
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import all test modules
from test_config import TestConfigFunctions
from test_signals import TestSignalGeneration
from test_noise import TestNoiseFunctions
from test_demod import TestDemodulation
from test_utils import TestUtilsFunctions


def run_all_tests():
    """Run all unit tests."""
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestConfigFunctions))
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestSignalGeneration))
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestNoiseFunctions))
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestDemodulation))
    test_suite.addTest(unittest.TestLoader().loadTestsFromTestCase(TestUtilsFunctions))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print(f"\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print(f"\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
