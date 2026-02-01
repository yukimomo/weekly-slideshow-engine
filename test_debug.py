#!/usr/bin/env python
"""簡単なデバッグ スクリプト"""

import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Test 1: Import check
print("=" * 60)
print("Test 1: Module Import Check")
print("=" * 60)
try:
    from video_engine import __version__
    print(f"✓ video_engine imported successfully")
    print(f"  Version: {__version__}")
except ImportError as e:
    print(f"✗ Failed to import video_engine: {e}")

# Test 2: Utils test
print("\n" + "=" * 60)
print("Test 2: iso_week_to_range Utility")
print("=" * 60)
try:
    from video_engine.utils import iso_week_to_range
    start, end = iso_week_to_range("2026-W04")
    print(f"✓ iso_week_to_range('2026-W04') works")
    print(f"  Start (Monday): {start}")
    print(f"  End (Sunday): {end}")
except Exception as e:
    print(f"✗ iso_week_to_range failed: {e}")

# Test 3: parse_exif_datetime test
print("\n" + "=" * 60)
print("Test 3: parse_exif_datetime Utility")
print("=" * 60)
try:
    from video_engine.utils import parse_exif_datetime
    dt = parse_exif_datetime("2026:01:22 14:30:45")
    print(f"✓ parse_exif_datetime works")
    print(f"  Parsed: {dt}")
except Exception as e:
    print(f"✗ parse_exif_datetime failed: {e}")

# Test 4: Check timeline module
print("\n" + "=" * 60)
print("Test 4: Timeline Module")
print("=" * 60)
try:
    from video_engine import timeline
    print(f"✓ timeline module imported")
except Exception as e:
    print(f"✗ Failed to import timeline: {e}")

# Test 5: Check scan module
print("\n" + "=" * 60)
print("Test 5: Scan Module")
print("=" * 60)
try:
    from video_engine import scan
    print(f"✓ scan module imported")
except Exception as e:
    print(f"✗ Failed to import scan: {e}")

# Test 6: Check render module
print("\n" + "=" * 60)
print("Test 6: Render Module")
print("=" * 60)
try:
    from video_engine import render
    print(f"✓ render module imported")
except Exception as e:
    print(f"✗ Failed to import render: {e}")

# Test 7: Check CLI
print("\n" + "=" * 60)
print("Test 7: CLI Module")
print("=" * 60)
try:
    from video_engine import cli
    print(f"✓ cli module imported")
except Exception as e:
    print(f"✗ Failed to import cli: {e}")

print("\n" + "=" * 60)
print("Basic Debugging Complete")
print("=" * 60)
