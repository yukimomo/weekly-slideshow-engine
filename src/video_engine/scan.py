"""Scanning utilities for video_engine.

Scan media files under input/YYYY-MM-DD directories for a week range and
extract capture timestamps (prefer EXIF for photos). Designed to be
robust for OneDrive-synced folders where mtime may be unreliable.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Literal

from .utils import parse_exif_datetime

logger = logging.getLogger(__name__)

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic"}
VIDEO_EXTS = {".mp4", ".mov"}

# Try to import Pillow (PIL) for EXIF reading; if unavailable, continue
try:
    from PIL import Image
    # Optional: enable HEIC/HEIF support when pillow-heif is installed
    try:
        import pillow_heif  # type: ignore

        try:
            pillow_heif.register_heif_opener()
        except Exception:
            pass
    except Exception:
        pass
except Exception:  # pragma: no cover - import failure path
    Image = None


@dataclass(frozen=True)
class MediaItem:
    path: Path
    kind: Literal["photo", "video"]
    timestamp: datetime


class ExclusionReason(str, Enum):
    directory = "directory"
    not_file = "not_file"
    extension = "extension"
    zero_byte = "zero_byte"
    unreadable = "unreadable"


@dataclass(frozen=True)
class ScanReport:
    input_root: Path
    input_exists: bool
    scan_all: bool
    photo_exts: tuple[str, ...]
    video_exts: tuple[str, ...]
    found_files: int
    excluded_counts: Dict[ExclusionReason, int]
    media_count: int
    sample_items: List[MediaItem]
    suggestions: List[Path]

    def excluded_total(self) -> int:
        return sum(self.excluded_counts.values())


def _read_photo_exif_timestamp(path: Path) -> datetime | None:
    if Image is None:
        logger.debug("Pillow not available; skipping EXIF read for %s", path)
        return None

    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return None

            # DateTimeOriginal tag (36867) or DateTime (306)
            dts = exif.get(36867) or exif.get(306)
            if not dts:
                return None

            try:
                return parse_exif_datetime(dts)
            except ValueError:
                logger.warning("Unparseable EXIF DateTime for %s: %r", path, dts)
                return None
    except Exception as exc:
        logger.warning("Failed to read EXIF from %s: %s", path, exc)
        return None


def _file_mtime_timestamp(path: Path) -> datetime:
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts)


def normalize_input_path(input_dir: Path) -> Path:
    text = str(input_dir).strip()
    if (text.startswith("\"") and text.endswith("\"")) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1]
    p = Path(text).expanduser()
    try:
        return p.resolve(strict=False)
    except Exception:
        return p


def _nearest_existing_parent(path: Path) -> Path | None:
    cur = path
    while True:
        if cur.exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def suggest_input_paths(path: Path, limit: int = 5) -> List[Path]:
    parent = _nearest_existing_parent(path)
    if parent is None or not parent.is_dir():
        return []
    try:
        candidates = [p for p in parent.iterdir() if p.is_dir()]
    except Exception:
        return []
    if not candidates:
        return []
    # Prefer name similarity when possible, otherwise return a few entries.
    try:
        import difflib

        names = [p.name for p in candidates]
        matches = difflib.get_close_matches(path.name, names, n=limit)
        if matches:
            return [parent / name for name in matches]
    except Exception:
        pass
    return candidates[:limit]


def _scan_paths(
    paths: Iterable[Path],
    sample_limit: int = 20,
) -> tuple[List[MediaItem], Counter[ExclusionReason], int]:
    items: List[MediaItem] = []
    excluded: Counter[ExclusionReason] = Counter()
    found_files = 0

    for p in paths:
        try:
            if p.is_dir():
                excluded[ExclusionReason.directory] += 1
                continue
            if not p.is_file():
                excluded[ExclusionReason.not_file] += 1
                continue
        except Exception:
            excluded[ExclusionReason.unreadable] += 1
            continue

        found_files += 1
        try:
            if p.stat().st_size == 0:
                excluded[ExclusionReason.zero_byte] += 1
                continue
        except Exception:
            excluded[ExclusionReason.unreadable] += 1
            continue

        ext = p.suffix.lower()
        kind: Literal["photo", "video"] | None = None
        if ext in PHOTO_EXTS:
            kind = "photo"
        elif ext in VIDEO_EXTS:
            kind = "video"
        else:
            excluded[ExclusionReason.extension] += 1
            continue

        ts: datetime | None = None
        if kind == "photo":
            ts = _read_photo_exif_timestamp(p)
            if ts is None:
                logger.debug("No EXIF timestamp for %s; fallback to mtime", p)
        if ts is None:
            ts = _file_mtime_timestamp(p)

        items.append(MediaItem(path=p, kind=kind, timestamp=ts))

    items.sort(key=lambda it: it.timestamp)
    if sample_limit <= 0:
        return items, excluded, found_files
    return items, excluded, found_files


def scan_media_with_report(
    input_dir: Path,
    scan_all: bool,
    sample_limit: int = 20,
) -> tuple[List[MediaItem], ScanReport]:
    normalized = normalize_input_path(input_dir)
    input_exists = normalized.exists() and normalized.is_dir()

    if not input_exists:
        report = ScanReport(
            input_root=normalized,
            input_exists=False,
            scan_all=scan_all,
            photo_exts=tuple(sorted(PHOTO_EXTS)),
            video_exts=tuple(sorted(VIDEO_EXTS)),
            found_files=0,
            excluded_counts={},
            media_count=0,
            sample_items=[],
            suggestions=suggest_input_paths(normalized),
        )
        return [], report

    if scan_all:
        items, excluded, found_files = _scan_paths(normalized.rglob("*"), sample_limit=sample_limit)
    else:
        items, excluded, found_files = _scan_paths(normalized.iterdir(), sample_limit=sample_limit)

    sample_items = items[:sample_limit] if sample_limit > 0 else []
    report = ScanReport(
        input_root=normalized,
        input_exists=True,
        scan_all=scan_all,
        photo_exts=tuple(sorted(PHOTO_EXTS)),
        video_exts=tuple(sorted(VIDEO_EXTS)),
        found_files=found_files,
        excluded_counts=dict(excluded),
        media_count=len(items),
        sample_items=sample_items,
        suggestions=[],
    )
    return items, report


def scan_week(input_dir: Path, start_date: date, end_date: date) -> List[MediaItem]:
    """Scan media files within dates from start_date..end_date (inclusive).

    For each existing `input/YYYY-MM-DD` directory, collect supported media
    files and extract timestamps with the following priority:
      1) Photo EXIF DateTimeOriginal (preferred)
      2) (Video creation timestamp if implemented)  -- not implemented yet
      3) Filename pattern (not implemented)
      4) File mtime (fallback)

    Returns a chronologically sorted list of MediaItem objects.
    """
    items: List[MediaItem] = []

    cur = start_date
    while cur <= end_date:
        day_dir = input_dir / cur.isoformat()
        if not day_dir.exists():
            logger.debug("Skipping missing directory %s", day_dir)
            cur = cur.fromordinal(cur.toordinal() + 1)
            continue

        for p in day_dir.iterdir():
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            kind: Literal["photo", "video"] | None = None
            if ext in PHOTO_EXTS:
                kind = "photo"
            elif ext in VIDEO_EXTS:
                kind = "video"
            else:
                continue

            ts: datetime | None = None

            # Preferred: EXIF for photos
            if kind == "photo":
                ts = _read_photo_exif_timestamp(p)
                if ts is None:
                    logger.debug("No EXIF timestamp for %s; will fallback to mtime", p)

            # TODO: add video creation timestamp extraction here

            if ts is None:
                ts = _file_mtime_timestamp(p)

            items.append(MediaItem(path=p, kind=kind, timestamp=ts))

        cur = cur.fromordinal(cur.toordinal() + 1)

    items.sort(key=lambda it: it.timestamp)
    return items


def scan_all(input_dir: Path) -> List[MediaItem]:
    """Recursively scan all supported media files under `input_dir`.

    - Photos: try EXIF DateTimeOriginal; fallback to file mtime
    - Videos: fallback to file mtime
    Returns a chronologically sorted list of MediaItem objects.
    """
    items, _report = scan_media_with_report(input_dir, scan_all=True, sample_limit=0)
    return items


def scan_flat(input_dir: Path) -> List[MediaItem]:
    """Scan only the top-level of `input_dir` (non-recursive).

    Collect supported photo/video files directly under `input_dir` and
    extract timestamps similarly to `scan_all`.
    """
    items, _report = scan_media_with_report(input_dir, scan_all=False, sample_limit=0)
    return items


def build_scan_summary_lines(report: ScanReport) -> List[str]:
    photo_exts = ",".join(report.photo_exts)
    video_exts = ",".join(report.video_exts)
    lines = [
        f"Scan input: {report.input_root}",
        f"Scan mode: {'recursive' if report.scan_all else 'flat'}",
        f"Allowed extensions: photos={photo_exts} videos={video_exts}",
        f"Files found: {report.found_files}, excluded: {report.excluded_total()}, media: {report.media_count}",
    ]
    if report.excluded_total() > 0:
        parts = []
        for reason in ExclusionReason:
            count = report.excluded_counts.get(reason, 0)
            if count:
                parts.append(f"{reason.value}={count}")
        if parts:
            lines.append("Excluded breakdown: " + ", ".join(parts))
    return lines


def build_no_media_message(report: ScanReport) -> List[str]:
    lines = ["no media found"]
    lines.extend(build_scan_summary_lines(report))

    if not report.input_exists:
        lines.append("Input path does not exist. Check the path or remove trailing quotes.")
        if report.suggestions:
            lines.append("Did you mean:")
            for p in report.suggestions:
                lines.append(f"  - {p}")

    hints = []
    if not report.scan_all:
        hints.append("Try --scan-all to include subfolders")
    hints.append("Confirm the input path and that files are downloaded (OneDrive placeholders)")
    hints.append("Check that file extensions are supported (photos: .jpg/.jpeg/.png/.heic, videos: .mp4/.mov)")
    lines.append("Next steps: " + "; ".join(hints))
    return lines
