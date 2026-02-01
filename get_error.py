#!/usr/bin/env python
"""Get detailed error information from a single test"""

import subprocess
import sys

# Run a simple test to see the error
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_utils.py", "-v", "--tb=short"],
    capture_output=True,
    text=True
)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")
