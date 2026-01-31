"""Minimal rendering utilities using MoviePy.

This module provides an MVP function to render a single photo to an MP4
video. The implementation is intentionally small and provides clear
error messages when dependencies are missing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def render_single_photo(photo_path: Path, output_path: Path, duration: float = 60.0, fps: int = 30) -> None:
    """Render a single photo as an MP4 video.

    Parameters
    - photo_path: Path to the source image file (must exist)
    - output_path: Path to write the MP4 file (parent directories will be created)
    - duration: duration of the output video in seconds (float)
    - fps: frames per second to write

    Raises
    - FileNotFoundError: if ``photo_path`` does not exist or is not a file
    - RuntimeError: if moviepy is not installed or rendering fails
    """
    if not photo_path.exists() or not photo_path.is_file():
        raise FileNotFoundError(f"Photo not found or not a file: {photo_path}")

    try:
        # Import lazily to provide clear errors when dependency is missing
        from moviepy.editor import ImageClip
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError("moviepy is required for rendering; install the 'render' extras (e.g., pip install -e \".[render]\"") from exc

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        clip = ImageClip(str(photo_path)).set_duration(float(duration))
        # Minimal write parameters: libx264, no audio
        clip.write_videofile(str(output_path), fps=int(fps), codec="libx264", audio=False, verbose=False, logger=None)
    except Exception as exc:  # pragma: no cover - depends on runtime ffmpeg
        raise RuntimeError(f"Failed to render video: {exc}") from exc
