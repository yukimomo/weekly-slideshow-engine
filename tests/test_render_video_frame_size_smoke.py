"""Smoke test to ensure rendered video frames are full-size (no small centered patch)."""

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


def _make_mp4(path: Path, duration: float = 0.5, fps: int = 10) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=blue:s=160x120:d={duration}",
        "-r",
        str(fps),
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: stdout={proc.stdout!r}\nstderr={proc.stderr!r}")


def _probe_size(path: Path) -> tuple[int, int]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe required for this test")
    proc = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True, timeout=20)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"ffprobe failed: stdout={proc.stdout!r}\nstderr={proc.stderr!r}")
    w, h = proc.stdout.strip().split("x")
    return int(w), int(h)


def test_rendered_video_has_expected_frame_size(tmp_path: Path) -> None:
    v = tmp_path / "t.mp4"
    _make_mp4(v, duration=0.5, fps=10)

    plans = [ClipPlan(path=v, kind="video", duration=0.5)]
    out = tmp_path / "out_frame.mp4"

    render_timeline(plans, out, fps=10, bgm_path=None)

    assert out.exists() and out.stat().st_size > 0

    w, h = _probe_size(out)
    # Expect OUT_W x OUT_H from render.py
    assert w == 1280 and h == 720


def test_preserve_videos_keeps_native_size_single(tmp_path: Path) -> None:
    v = tmp_path / "t_small.mp4"
    _make_mp4(v, duration=0.5, fps=10)

    plans = [ClipPlan(path=v, kind="video", duration=0.5)]
    out = tmp_path / "out_frame_preserve.mp4"

    render_timeline(plans, out, fps=10, bgm_path=None, preserve_videos=True)

    assert out.exists() and out.stat().st_size > 0

    w, h = _probe_size(out)
    # Expect native size (160x120)
    assert w == 160 and h == 120


def test_preserve_videos_uses_max_video_size(tmp_path: Path) -> None:
    # Create two videos with different sizes
    v1 = tmp_path / "v1.mp4"
    v2 = tmp_path / "v2.mp4"
    # small
    cmd1 = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=blue:s=160x120:d=0.5",
        "-r",
        "10",
        str(v1),
    ]
    subprocess.run(cmd1, capture_output=True, check=True, timeout=20)
    # larger
    cmd2 = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=red:s=320x240:d=0.5",
        "-r",
        "10",
        str(v2),
    ]
    subprocess.run(cmd2, capture_output=True, check=True, timeout=20)

    plans = [ClipPlan(path=v1, kind="video", duration=0.5), ClipPlan(path=v2, kind="video", duration=0.5)]
    out = tmp_path / "out_frame_preserve2.mp4"

    render_timeline(plans, out, fps=10, bgm_path=None, preserve_videos=True)

    assert out.exists() and out.stat().st_size > 0
    w, h = _probe_size(out)
    # Expect the max of widths/heights (320x240)
    assert w == 320 and h == 240


def test_rendered_mixed_has_expected_frame_size(tmp_path: Path) -> None:
    # video with surrounding photos
    p1 = tmp_path / "a.png"
    p2 = tmp_path / "b.png"
    try:
        from PIL import Image

        Image.new("RGB", (16, 16), color="green").save(p1)
        Image.new("RGB", (16, 16), color="orange").save(p2)
    except Exception:
        p1.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")
        p2.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")

    v = tmp_path / "t2.mp4"
    _make_mp4(v, duration=0.5, fps=10)

    plans = [ClipPlan(path=p1, kind="photo", duration=0.5), ClipPlan(path=v, kind="video", duration=0.5), ClipPlan(path=p2, kind="photo", duration=0.5)]
    out = tmp_path / "out_mixed_frame.mp4"

    render_timeline(plans, out, fps=10, bgm_path=None)

    assert out.exists() and out.stat().st_size > 0
    w, h = _probe_size(out)
    assert w == 1280 and h == 720
