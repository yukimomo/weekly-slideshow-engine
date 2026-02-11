"""Tests for `video_engine.scan` utilities."""

from __future__ import annotations

import os
import time
from datetime import date, datetime
from pathlib import Path

import pytest

from video_engine.scan import (
    ExclusionReason,
    MediaItem,
    normalize_input_path,
    scan_media_with_report,
    scan_week,
)


def _write_minimal_jpeg(path: Path) -> None:
    # Write a tiny valid JPEG header; not a full image but pillow can open it
    path.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100 + b"\xFF\xD9")


def test_photo_without_exif_uses_mtime(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    date_dir = input_dir / "2026-01-22"
    date_dir.mkdir(parents=True)

    f = date_dir / "img1.jpg"
    _write_minimal_jpeg(f)

    # Set mtime to a specific epoch time
    ts = 1674360000.0  # some fixed timestamp
    os.utime(f, (ts, ts))

    start = date(2026, 1, 19)  # week containing 2026-01-22
    end = date(2026, 1, 25)

    items = scan_week(input_dir, start, end)

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, MediaItem)
    assert item.path == f
    assert item.kind == "photo"
    assert item.timestamp == datetime.fromtimestamp(ts)


def test_missing_directory_no_crash(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    # Do not create any directories

    start = date(2026, 1, 19)
    end = date(2026, 1, 25)

    items = scan_week(input_dir, start, end)
    assert items == []


def test_sorting_by_timestamp(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    date_dir = input_dir / "2026-01-22"
    date_dir.mkdir(parents=True)

    f1 = date_dir / "a.jpg"
    f2 = date_dir / "b.jpg"
    _write_minimal_jpeg(f1)
    _write_minimal_jpeg(f2)

    # Set different mtimes
    os.utime(f1, (1000.0, 1000.0))
    os.utime(f2, (2000.0, 2000.0))

    start = date(2026, 1, 19)
    end = date(2026, 1, 25)

    items = scan_week(input_dir, start, end)

    assert [it.path for it in items] == [f1, f2]


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("PIL") is None,
    reason="Pillow not available",
)
def test_exif_date_used_if_present(tmp_path: Path) -> None:
    # If Pillow is available, create an image with EXIF DateTimeOriginal and ensure it is used
    from PIL import Image

    input_dir = tmp_path / "input"
    date_dir = input_dir / "2026-01-22"
    date_dir.mkdir(parents=True)

    f = date_dir / "with_exif.jpg"

    im = Image.new("RGB", (10, 10), color="red")

    # Pillow 12.x compatible EXIF writing
    exif = Image.Exif()
    exif[36867] = "2026:01:22 12:34:56"  # DateTimeOriginal
    im.save(f, exif=exif)

    start = date(2026, 1, 19)
    end = date(2026, 1, 25)

    items = scan_week(input_dir, start, end)
    assert len(items) == 1
    assert items[0].timestamp == datetime(2026, 1, 22, 12, 34, 56)


def test_scan_media_with_report_counts(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    jpg = input_dir / "photo.jpg"
    _write_minimal_jpeg(jpg)

    mp4 = input_dir / "clip.mp4"
    mp4.write_bytes(b"x")

    txt = input_dir / "notes.txt"
    txt.write_text("hello", encoding="utf-8")

    zero = input_dir / "empty.mov"
    zero.write_bytes(b"")

    (input_dir / "subdir").mkdir()

    items, report = scan_media_with_report(input_dir, scan_all=False, sample_limit=10)

    assert report.input_exists is True
    assert report.scan_all is False
    assert report.found_files == 4
    assert report.media_count == 2
    assert len(items) == 2
    assert report.excluded_counts.get(ExclusionReason.extension, 0) == 1
    assert report.excluded_counts.get(ExclusionReason.zero_byte, 0) == 1
    assert report.excluded_counts.get(ExclusionReason.directory, 0) == 1


def test_scan_media_with_report_recursive(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    nested = input_dir / "nested"
    nested.mkdir(parents=True)

    jpg = nested / "photo.jpg"
    _write_minimal_jpeg(jpg)

    items, report = scan_media_with_report(input_dir, scan_all=True, sample_limit=5)

    assert report.scan_all is True
    assert report.media_count == 1
    assert items[0].path == jpg


def test_scan_media_with_report_empty_dir(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    items, report = scan_media_with_report(input_dir, scan_all=False, sample_limit=5)

    assert items == []
    assert report.input_exists is True
    assert report.media_count == 0


def test_normalize_input_path_strips_quotes(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    quoted = Path(f'"{input_dir}"')

    normalized = normalize_input_path(quoted)
    assert normalized == input_dir.resolve()


def test_scan_report_suggests_paths(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "input_real").mkdir()

    missing = parent / "input_reel"
    _items, report = scan_media_with_report(missing, scan_all=False, sample_limit=5)

    assert report.input_exists is False
    assert report.suggestions
