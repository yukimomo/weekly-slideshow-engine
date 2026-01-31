"""Smoke test for concatenating multiple clips into a single MP4."""

from __future__ import annotations

import shutil
import math
from pathlib import Path
import sys
import subprocess

import pytest
import conftest

from video_engine.timeline import ClipPlan
from video_engine.render import render_timeline

pytestmark = [
    pytest.mark.skipif(not conftest.moviepy_usable(), reason="moviepy not usable (partial/misinstalled)"),
    pytest.mark.skipif(not conftest.ffmpeg_available(), reason="ffmpeg not available in PATH"),
]


def test_render_concat_two_photos(tmp_path: Path) -> None:

    # Create two small images
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    try:
        from PIL import Image

        Image.new("RGB", (16, 16), color="red").save(p1)
        Image.new("RGB", (16, 16), color="blue").save(p2)
    except Exception:
        p1.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")
        p2.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")

    plans = [ClipPlan(path=p1, kind="photo", duration=0.5), ClipPlan(path=p2, kind="photo", duration=0.5)]

    out = tmp_path / "out_concat.mp4"
    render_timeline(plans, out, fps=10, bgm_path=None)

    assert out.exists() and out.stat().st_size > 0

    # Optional duration check with ffprobe
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out)], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0 and proc.stdout:
            dur = float(proc.stdout.strip())
            assert abs(dur - 1.0) < 0.3
