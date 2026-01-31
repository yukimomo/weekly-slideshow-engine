"""Smoke test that verifies video clips can be preserved at original duration when requested."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import conftest
from video_engine.timeline import ClipPlan
from video_engine.render import render_timeline

pytestmark = [
    pytest.mark.skipif(not conftest.moviepy_usable(), reason="moviepy not usable (partial/misinstalled)"),
    pytest.mark.skipif(not conftest.ffmpeg_available(), reason="ffmpeg not available in PATH"),
]


def _make_mp4(path: Path, duration: float = 1.5, fps: int = 10) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=purple:s=160x120:d={duration}",
        "-r",
        str(fps),
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: stdout={proc.stdout!r}\nstderr={proc.stderr!r}")


def test_preserve_video_duration(tmp_path: Path) -> None:
    # One photo, one video, one photo; the video file is longer than the planned duration.
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    v = tmp_path / "long.mp4"

    # Tiny PNG placeholders (prefer Pillow if available)
    try:
        from PIL import Image

        Image.new("RGB", (16, 16), color="green").save(p1)
        Image.new("RGB", (16, 16), color="orange").save(p2)
    except Exception:
        p1.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")
        p2.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")

    # Make a longer video (1.5s), but plan will ask for 0.5s
    _make_mp4(v, duration=1.5, fps=10)

    plans = [
        ClipPlan(path=p1, kind="photo", duration=0.5),
        ClipPlan(path=v, kind="video", duration=0.5),
        ClipPlan(path=p2, kind="photo", duration=0.5),
    ]

    out = tmp_path / "out_preserve.mp4"
    render_timeline(plans, out, fps=10, bgm_path=None, preserve_videos=True)

    assert out.exists() and out.stat().st_size > 0

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(out)], capture_output=True, text=True, timeout=20)
        if proc.returncode == 0 and proc.stdout:
            dur = float(proc.stdout.strip())
            # Expect approx 0.5 + 1.5 + 0.5 = 2.5 seconds (allow some tolerance)
            assert abs(dur - 2.5) < 0.6
