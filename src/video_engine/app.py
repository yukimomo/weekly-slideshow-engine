"""Orchestration for end-to-end preview rendering.

Provides a `run_e2e` function that scans media for a given ISO week,
builds a short timeline and renders a preview MP4 using the first photo
clip (MVP behavior).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List

from .presets import DEFAULTS
from .scan import (
    MediaItem,
    ScanReport,
    build_no_media_message,
    build_scan_summary_lines,
    scan_media_with_report,
)
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
    week: str | None,
    input_dir: Path,
    bgm: Path | None,
    output_dir: Path,
    duration: float = float(DEFAULTS["duration"]),
    fps: int = 30,
    transition: float = float(DEFAULTS["transition"]),
    fade_max_ratio: float = 1.0,
    preserve_videos: bool = False,
    bg_blur: float = float(DEFAULTS["bg_blur"]),
    bgm_volume: float = float(DEFAULTS["bgm_volume"]),
    resolution: tuple[int, int] | None = None,
    scan_all_flag: bool = False,
    pre_scanned: List[MediaItem] | None = None,
    scan_report: ScanReport | None = None,
) -> int:
    """Run a minimal end-to-end preview creation for the given ISO week.

    Returns an exit code (0 success, 2 no media found).
    """
    # Simplified: scan current folder (non-recursive) by default; use recursive when requested.
    if pre_scanned is None or scan_report is None:
        items, report = scan_media_with_report(input_dir, scan_all=scan_all_flag, sample_limit=20)
    else:
        items, report = pre_scanned, scan_report
    if not items:
        for line in build_no_media_message(report):
            print(line)
        return 2

    for line in build_scan_summary_lines(report):
        print(line)

    plans = build_timeline(items, target_seconds=duration)

    # Ensure output dir exists
    output_dir.mkdir(parents=True, exist_ok=True)
    # Output filename: prefer provided week string; else use folder name
    if week:
        week_s = _sanitize_week(week)
        out_path = output_dir / f"{week_s}_preview.mp4"
    else:
        out_path = output_dir / f"{input_dir.name}_preview.mp4"

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
        fade_max_ratio=fade_max_ratio,
        preserve_videos=preserve_videos,
        bg_blur=bg_blur,
        bgm_volume=bgm_volume,
        resolution=resolution,
    )

    print(f"Wrote preview: {out_path}")
    return 0
