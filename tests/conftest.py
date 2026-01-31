"""Test configuration to ensure local `src/` is discoverable during tests."""

from __future__ import annotations

import sys
from pathlib import Path
import shutil

# Prepend the project's `src/` directory so local package modules are used
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def ffmpeg_available() -> bool:
    """Return True when an `ffmpeg` binary is available on PATH."""
    return shutil.which("ffmpeg") is not None


def moviepy_usable() -> bool:
    """Return True only if MoviePy is importable and exposes the symbols
    required by our rendering helpers. This avoids partial/incorrect MoviePy
    installs causing test failures (we prefer skipping in that case).
    """
    try:
        # Prefer the convenient editor import used commonly in MoviePy 2.x
        try:
            from moviepy.editor import ImageClip, VideoFileClip, concatenate_videoclips, AudioFileClip  # type: ignore
            return True
        except Exception:
            # Try common fallbacks used in older/newer layouts
            from moviepy.video.VideoClip import ImageClip  # type: ignore
            from moviepy.video.io.VideoFileClip import VideoFileClip  # type: ignore
            try:
                from moviepy.video.compositing.concatenate import concatenate_videoclips  # type: ignore
            except Exception:
                try:
                    from moviepy.video.tools.cuts import concatenate_videoclips  # type: ignore
                except Exception:
                    return False
            try:
                from moviepy.audio.io.AudioFileClip import AudioFileClip  # type: ignore
            except Exception:
                return False
            return True
    except Exception:
        return False
