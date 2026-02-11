
from __future__ import annotations
import re
"""Command-line interface for the video_engine package.

This module provides a minimal, extensible argparse-based CLI skeleton
with a `build_parser()` factory and `main()` entry point.
"""

import argparse
from pathlib import Path
import sys
from typing import List, Optional


def build_parser() -> argparse.ArgumentParser:
    def parse_resolution(s):
        if s is None:
            return None
        m = re.match(r"^(\d{2,5})x(\d{2,5})$", s)
        if not m:
            raise argparse.ArgumentTypeError("--resolution must be in WIDTHxHEIGHT format, e.g. 1920x1080")
        w, h = int(m.group(1)), int(m.group(2))
        if w < 320 or h < 240 or w > 8192 or h > 4320:
            raise argparse.ArgumentTypeError("--resolution values out of supported range (min 320x240, max 8192x4320)")
        return (w, h)

    parser = argparse.ArgumentParser(
        prog="video_engine",
        description="Weekly slideshow engine (skeleton CLI).",
    )

    def parse_scan_limit(value: str) -> int:
        try:
            v = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("--scan-limit must be an integer") from exc
        if v < 0:
            raise argparse.ArgumentTypeError("--scan-limit must be >= 0")
        return v

    parser.add_argument(
        "--resolution",
        type=parse_resolution,
        default=None,
        help="Output resolution as WIDTHxHEIGHT (e.g. 1920x1080). Default: 1280x720 or auto."
    )

    parser.add_argument(
        "--preset",
        type=str,
        choices=["youtube", "mobile", "preview"],
        help="Apply a preset of defaults (youtube, mobile, preview). Explicit flags override preset values."
    )

    parser.add_argument(
        "--name",
        "--week",
        dest="name",
        type=str,
        help="Optional name used for output filename (e.g. 2026-W04)",
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=Path("./input"),
        help="Path to input directory (default: ./input)",
    )

    parser.add_argument(
        "--bgm",
        type=Path,
        default=Path("./bgm"),
        help="Path to background music directory (default: ./bgm)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./output"),
        help="Path to output directory (default: ./output)",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=8.0,
        help="Duration in seconds for the preview video (default: 8.0)",
    )

    parser.add_argument(
        "--transition",
        type=float,
        default=0.3,
        help="Per-clip transition length in seconds (fade-in/out, default: 0.3). Set 0 to disable.",
    )

    parser.add_argument(
        "--fade-max-ratio",
        type=float,
        default=1.0,
        help="Max fade duration as a ratio of clip length (default: 1.0 = no cap).",
    )

    parser.add_argument(
        "--preserve-videos",
        action="store_true",
        help="When set, include video files at their original duration instead of trimming to planned duration.",
    )

    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan all photos/videos under input directory recursively instead of ISO week subfolders.",
    )

    parser.add_argument(
        "--verbose-scan",
        "--debug-scan",
        dest="verbose_scan",
        action="store_true",
        help="Show detailed scan logs, including sample media items and exclusion counts.",
    )

    parser.add_argument(
        "--scan-limit",
        type=parse_scan_limit,
        default=20,
        help="Maximum number of media items to display in verbose scan output (default: 20).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making changes.",
    )

    parser.add_argument(
        "--bg-blur",
        type=float,
        default=6.0,
        help="Blur radius for background of portrait photos (default: 6.0, set 0 to disable)",
    )

    parser.add_argument(
        "--bgm-volume",
        type=float,
        default=10.0,
        help="BGM volume level as percentage of original video audio (default: 10.0, range: 0-200)",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point.

    Parses arguments and returns an exit code. No application logic is
    implemented yet; this function only demonstrates argument parsing and
    a friendly startup message.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Apply preset defaults, then let explicit CLI flags override.
    from .presets import merge_preset, detect_provided_options
    argv_tokens = argv if argv is not None else sys.argv[1:]
    # Backward-compat: when no arguments at all, require --name to guide usage
    if not argv_tokens:
        parser.error("argument --name is required")
    provided = detect_provided_options(argv_tokens)
    base = {
        "resolution": args.resolution,
        "duration": float(args.duration),
        "transition": float(args.transition),
        "bg_blur": float(args.bg_blur),
        "bgm_volume": float(args.bgm_volume),
    }
    effective = merge_preset(getattr(args, "preset", None), base, provided)
    # Reflect effective values back to args
    args.resolution = effective.get("resolution", args.resolution)
    args.duration = float(effective.get("duration", args.duration))
    args.transition = float(effective.get("transition", args.transition))
    args.bg_blur = float(effective.get("bg_blur", args.bg_blur))
    args.bgm_volume = float(effective.get("bgm_volume", args.bgm_volume))

    # Week is optional; scanning behavior controlled by --scan-all

    # Prepare app entry
    from .app import run_e2e
    from .scan import build_no_media_message, build_scan_summary_lines, scan_media_with_report

    scan_items = None
    scan_report = None
    if args.dry_run or args.verbose_scan:
        scan_items, scan_report = scan_media_with_report(
            args.input,
            scan_all=bool(args.scan_all),
            sample_limit=int(args.scan_limit),
        )

    if args.dry_run:
        # Dry run: report what would happen
        from .timeline import build_timeline
        items = scan_items or []
        report = scan_report
        if report is not None:
            if report.media_count == 0:
                for line in build_no_media_message(report):
                    print(line)
            else:
                for line in build_scan_summary_lines(report):
                    print(line)
                if args.scan_limit != 0:
                    print(f"Sample media (first {min(len(report.sample_items), args.scan_limit)}):")
                    for it in report.sample_items:
                        print(f"  - {it.kind} {it.timestamp.isoformat()} {it.path}")

        plans = build_timeline(items, target_seconds=float(args.duration))
        # Choose bgm summary
        bgm_choice = None
        if args.bgm and args.bgm.exists():
            if args.bgm.is_file():
                bgm_choice = args.bgm
            else:
                files = sorted([p for p in args.bgm.iterdir() if p.is_file()])
                bgm_choice = files[0] if files else None

        print(f"Timeline entries: {len(plans)}")
        print(f"Chosen BGM: {bgm_choice}")
        # Preset summary + effective values
        print(f"Preset: {getattr(args, 'preset', None) or 'none'}")
        eff_res = args.resolution
        res_txt = f"{eff_res[0]}x{eff_res[1]}" if eff_res else "default"
        print(f"Effective resolution: {res_txt}")
        print(f"Effective duration: {float(args.duration)}s")
        print(f"Effective transition: {float(args.transition)}s")
        print(f"Effective bg_blur: {float(args.bg_blur)}")
        print(f"Effective bgm_volume: {float(args.bgm_volume)}%")
        return 0

    if args.verbose_scan and scan_report is not None:
        if scan_report.media_count > 0 and args.scan_limit != 0:
            print(f"Sample media (first {min(len(scan_report.sample_items), args.scan_limit)}):")
            for it in scan_report.sample_items:
                print(f"  - {it.kind} {it.timestamp.isoformat()} {it.path}")

    # Non-dry run: run end-to-end
    if scan_items is not None and scan_report is not None:
        return run_e2e(
            args.name,
            args.input,
            args.bgm,
            args.output,
            duration=float(args.duration),
            fps=30,
            transition=float(args.transition),
            fade_max_ratio=float(args.fade_max_ratio),
            preserve_videos=bool(args.preserve_videos),
            bg_blur=float(args.bg_blur),
            bgm_volume=float(args.bgm_volume),
            resolution=args.resolution,
            scan_all_flag=bool(args.scan_all),
            pre_scanned=scan_items,
            scan_report=scan_report,
        )

    rc = run_e2e(
        args.name,
        args.input,
        args.bgm,
        args.output,
        duration=float(args.duration),
        fps=30,
        transition=float(args.transition),
        fade_max_ratio=float(args.fade_max_ratio),
        preserve_videos=bool(args.preserve_videos),
        bg_blur=float(args.bg_blur),
        bgm_volume=float(args.bgm_volume),
        resolution=args.resolution,
        scan_all_flag=bool(args.scan_all),
    )
    return rc
