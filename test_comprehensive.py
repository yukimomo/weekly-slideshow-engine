#!/usr/bin/env python
"""統合デバッグ スクリプト - 全機能テスト"""

import sys
from pathlib import Path
from datetime import date, datetime

# Add src to path
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

print("=" * 70)
print("COMPREHENSIVE VIDEO ENGINE DEBUG TEST")
print("=" * 70)

# Test 1: Timeline functionality
print("\n[TEST 1] Timeline Module - Building timelines")
print("-" * 70)
try:
    from video_engine.timeline import build_timeline, ClipPlan
    from video_engine.scan import MediaItem
    
    # Create test items
    test_items = [
        MediaItem(path=Path(f"photo_{i}.jpg"), kind="photo", timestamp=datetime(2026, 1, 22, 10, 0, i))
        for i in range(10)
    ]
    
    plans = build_timeline(test_items, target_seconds=60.0, photo_seconds=2.5, photo_max_seconds=6.0)
    total_duration = sum(p.duration for p in plans)
    
    print(f"✓ Timeline creation successful")
    print(f"  Input: {len(test_items)} photos")
    print(f"  Output: {len(plans)} clip plans")
    print(f"  Total duration: {total_duration:.2f}s (target: 60.0s)")
    print(f"  Duration deviation: {abs(total_duration - 60.0):.6f}s")
    
    if len(plans) > 0:
        print(f"  First clip duration: {plans[0].duration:.2f}s")
        print(f"  Last clip duration: {plans[-1].duration:.2f}s")
    
except Exception as e:
    print(f"✗ Timeline test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Presets functionality
print("\n[TEST 2] Presets Module - Configuration merging")
print("-" * 70)
try:
    from video_engine.presets import merge_preset, detect_provided_options
    
    # Test merge with preset
    base_config = {
        "resolution": None,
        "duration": 60.0,
        "transition": 0.1,
        "bg_blur": 0.0,
    }
    
    merged = merge_preset("youtube", base_config, set())
    print(f"✓ Preset merging successful")
    print(f"  Base resolution: {base_config['resolution']}")
    print(f"  After 'youtube' preset: {merged['resolution']}")
    print(f"  Preset transition: {merged['transition']}")
    print(f"  Preset bg_blur: {merged['bg_blur']}")
    
    # Test CLI option detection
    test_argv = ["program", "--resolution", "1920x1080", "--duration=30"]
    provided = detect_provided_options(test_argv)
    print(f"  CLI options detected: {provided}")
    
except Exception as e:
    print(f"✗ Presets test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Scan functionality
print("\n[TEST 3] Scan Module - Directory scanning")
print("-" * 70)
try:
    from video_engine.scan import scan_week, MediaItem
    from pathlib import Path
    from datetime import date
    import tempfile
    import os
    
    # Create temporary test structure
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_dir = tmpdir_path / "input"
        date_dir = input_dir / "2026-01-22"
        date_dir.mkdir(parents=True)
        
        # Create a minimal JPEG
        test_file = date_dir / "test_photo.jpg"
        test_file.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100 + b"\xFF\xD9")
        
        # Set modification time
        ts = 1674360000.0
        os.utime(test_file, (ts, ts))
        
        # Scan the week
        start = date(2026, 1, 19)
        end = date(2026, 1, 25)
        items = scan_week(input_dir, start, end)
        
        print(f"✓ Scan successful")
        print(f"  Scanned range: {start} to {end}")
        print(f"  Found items: {len(items)}")
        if items:
            item = items[0]
            print(f"  First item: {item.path.name}")
            print(f"  Kind: {item.kind}")
            print(f"  Timestamp: {item.timestamp}")
    
except Exception as e:
    print(f"✗ Scan test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Utils functionality
print("\n[TEST 4] Utils Module - Utilities")
print("-" * 70)
try:
    from video_engine.utils import iso_week_to_range, parse_exif_datetime
    
    # Test ISO week parsing
    start, end = iso_week_to_range("2026-W04")
    print(f"✓ ISO week parsing successful")
    print(f"  Week 2026-W04: {start} (Mon) to {end} (Sun)")
    
    # Test EXIF datetime parsing
    dt = parse_exif_datetime("2026:01:22 14:30:45")
    print(f"✓ EXIF datetime parsing successful")
    print(f"  Parsed: {dt}")
    
    # Test error handling
    try:
        parse_exif_datetime("invalid-date")
        print(f"✗ Should have raised ValueError for invalid date")
    except ValueError:
        print(f"✓ Properly raises ValueError for invalid EXIF format")
    
except Exception as e:
    print(f"✗ Utils test failed: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Module imports
print("\n[TEST 5] All Module Imports")
print("-" * 70)
try:
    modules_to_test = ['__init__', 'utils', 'timeline', 'scan', 'render', 'cli', 'presets', '__main__', 'app']
    successful = []
    failed = []
    
    for mod in modules_to_test:
        try:
            __import__(f'video_engine.{mod}')
            successful.append(mod)
        except Exception as e:
            failed.append((mod, str(e)))
    
    print(f"✓ Successfully imported {len(successful)}/{len(modules_to_test)} modules")
    print(f"  Imported: {', '.join(successful)}")
    if failed:
        print(f"  Failed imports:")
        for mod, err in failed:
            print(f"    - {mod}: {err[:60]}...")
    
except Exception as e:
    print(f"✗ Module import test failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DEBUG TEST COMPLETE")
print("=" * 70)
