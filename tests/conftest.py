"""Test configuration to ensure local `src/` is discoverable during tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Prepend the project's `src/` directory so local package modules are used
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
