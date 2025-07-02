#!/usr/bin/env python3
"""Simple test runner for Xcel Energy Tariff integration."""

import sys
import subprocess
from pathlib import Path

def run_tests():
    """Run the test suite."""
    print("Running Xcel Energy Tariff Integration Tests")
    print("=" * 50)
    
    # Check if pytest is installed
    try:
        import pytest
    except ImportError:
        print("ERROR: pytest is not installed")
        print("Please run: pip install pytest pytest-asyncio pytest-mock")
        return 1
    
    # Run tests with coverage if available
    test_dir = Path(__file__).parent / "tests"
    
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_dir),
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
    ]
    
    try:
        # Check if pytest-cov is available
        import pytest_cov
        cmd.extend([
            "--cov=custom_components.xcel_energy_tariff",
            "--cov-report=term-missing",
        ])
    except ImportError:
        print("Note: Install pytest-cov for coverage reporting")
    
    # Run the tests
    result = subprocess.run(cmd)
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_tests())