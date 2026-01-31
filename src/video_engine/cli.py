"""Command-line interface for the video_engine package.

This module provides a minimal, extensible argparse-based CLI skeleton
with a `build_parser()` factory and `main()` entry point.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser.

    The parser is intentionally simple and designed to be extended with
    subcommands in the future.
    """
    parser = argparse.ArgumentParser(
        prog="video_engine",
        description="Weekly slideshow engine (skeleton CLI).",
    )

    parser.add_argument(
        "--week",
        type=str,
        help="ISO week string, e.g. 2026-W04",
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
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making changes.",
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

    # Require week for now
    if not args.week:
        parser.error("argument --week is required")

    # Compute week range
    from .app import run_e2e
    from .utils import iso_week_to_range

    start, end = iso_week_to_range(args.week)

    if args.dry_run:
        # Dry run: report what would happen
        from .scan import scan_week
        from .timeline import build_timeline

        items = scan_week(args.input, start, end)
        plans = build_timeline(items, target_seconds=float(args.duration))
        # Choose bgm summary
        bgm_choice = None
        if args.bgm and args.bgm.exists():
            if args.bgm.is_file():
                bgm_choice = args.bgm
            else:
                files = sorted([p for p in args.bgm.iterdir() if p.is_file()])
                bgm_choice = files[0] if files else None

        print(f"Week: {args.week} -> {start.isoformat()}..{end.isoformat()}")
        print(f"Input dir: {args.input} - found {len(items)} media items")
        print(f"Timeline entries: {len(plans)}")
        print(f"Chosen BGM: {bgm_choice}")
        print(f"Transition: {float(args.transition)}s")
        return 0

    # Non-dry run: run end-to-end
    rc = run_e2e(args.week, args.input, args.bgm, args.output, duration=float(args.duration), fps=30)
    return rc
