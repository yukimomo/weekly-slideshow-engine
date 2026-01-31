"""Orchestration for end-to-end preview rendering.

Provides a `run_e2e` function that scans media for a given ISO week,
builds a short timeline and renders a preview MP4 using the first photo
clip (MVP behavior).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .utils import iso_week_to_range
from .scan import scan_week
from .timeline import build_timeline
from .render import render_single_photo


def _sanitize_week(iso_week: str) -> str:
    # Keep only safe characters
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in iso_week)


def _choose_bgm(bgm_path: Path | None) -> Optional[Path]:
    if bgm_path is None:
        return None
    if bgm_path.is_file():
        return bgm_path
    if bgm_path.is_dir():
        files = sorted([p for p in bgm_path.iterdir() if p.is_file()])
        return files[0] if files else None
    return None


def run_e2e(
    week: str,
    input_dir: Path,
    bgm: Path | None,
    output_dir: Path,
    duration: float = 8.0,
    fps: int = 30,
    transition: float = 0.3,
    preserve_videos: bool = False,
) -> int:
    """Run a minimal end-to-end preview creation for the given ISO week.

    Returns an exit code (0 success, 2 no media found).
    """
    start_date, end_date = iso_week_to_range(week)

    items = scan_week(input_dir, start_date, end_date)
    if not items:
        print("no media found")
        return 2

    plans = build_timeline(items, target_seconds=duration)

    # Ensure output dir exists
    output_dir.mkdir(parents=True, exist_ok=True)
    week_s = _sanitize_week(week)
    out_path = output_dir / f"{week_s}_preview.mp4"

    bgm_choice = _choose_bgm(bgm)

    # Render full timeline by concatenating the planned clips
    from .render import render_timeline

    render_timeline(
        plans,
        out_path,
        fps=fps,
        bgm_path=bgm_choice,
        fade_in=0.5,
        fade_out=0.5,
        transition=transition,
        preserve_videos=preserve_videos,
    )

    print(f"Wrote preview: {out_path}")
    return 0
