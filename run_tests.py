#!/usr/bin/env python
"""Minimal pytest runner setup"""

import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Try running pytest
if __name__ == "__main__":
    try:
        import pytest
        exit_code = pytest.main([
            "tests/",
            "-v",
            "--tb=short",
            "-ra"
        ])
        sys.exit(exit_code)
    except ImportError:
        print("pytest is not installed. Installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pytest"])
        import pytest
        exit_code = pytest.main([
            "tests/",
            "-v",
            "--tb=short",
            "-ra"
        ])
        sys.exit(exit_code)
