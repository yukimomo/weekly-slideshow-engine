"""Scanning utilities for video_engine.

Scan media files under input/YYYY-MM-DD directories for a week range and
extract capture timestamps (prefer EXIF for photos). Designed to be
robust for OneDrive-synced folders where mtime may be unreliable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
from typing import List, Literal

from .utils import parse_exif_datetime

logger = logging.getLogger(__name__)

PHOTO_EXTS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTS = {".mp4", ".mov"}

# Try to import Pillow (PIL) for EXIF reading; if unavailable, continue
try:
    from PIL import Image
except Exception:  # pragma: no cover - import failure path
    Image = None


@dataclass(frozen=True)
class MediaItem:
    path: Path
    kind: Literal["photo", "video"]
    timestamp: datetime


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
