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
    _ = parser.parse_args(argv)

    # Minimal runtime behavior for the MVP skeleton.
    print("video_engine initialized (MVP). This is a skeleton CLI.")
    return 0
