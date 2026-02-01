#!/usr/bin/env python
"""Quick test to identify which tests are hanging"""

import subprocess
import sys
import os
from pathlib import Path

# Set timeout for tests (in seconds)
TIMEOUT = 30

# Get list of test files
test_dir = Path("tests")
test_files = sorted(test_dir.glob("test_*.py"))

print("=" * 70)
print("TESTING INDIVIDUAL TEST FILES WITH TIMEOUT")
print("=" * 70)

results = {
    "passed": [],
    "timeout": [],
    "failed": [],
    "skipped": []
}

for test_file in test_files:
    test_name = test_file.name
    print(f"\n[{test_name}] Running with {TIMEOUT}s timeout...", end=" ", flush=True)
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=line", "-q"],
            timeout=TIMEOUT,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd())
        )
        
        if result.returncode == 0:
            # Check if tests were skipped
            if "skipped" in result.stdout:
                print(f"SKIPPED")
                results["skipped"].append(test_name)
            else:
                print(f"PASSED")
                results["passed"].append(test_name)
        elif result.returncode == 5:
            # pytest exit code 5 means no tests collected (all skipped)
            print(f"SKIPPED (no tests)")
            results["skipped"].append(test_name)
        else:
            print(f"FAILED")
            results["failed"].append(test_name)
            # Print first few lines of error
            lines = result.stdout.split('\n')[:3]
            for line in lines:
                if line.strip():
                    print(f"  {line[:60]}")
    
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT ({TIMEOUT}s)")
        results["timeout"].append(test_name)
    except Exception as e:
        print(f"ERROR: {e}")
        results["failed"].append(test_name)

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"✓ Passed:  {len(results['passed'])} - {results['passed']}")
print(f"⏱ Timeout: {len(results['timeout'])} - {results['timeout']}")
print(f"✗ Failed:  {len(results['failed'])} - {results['failed']}")
print(f"⊘ Skipped: {len(results['skipped'])} - {results['skipped']}")

if results['timeout']:
    print("\n⚠ Tests that timeout (likely hanging):")
    for test in results['timeout']:
        print(f"  - {test}")
