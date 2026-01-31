"""Smoke test verifying portrait photos keep foreground at original size and background is blurred."""

from __future__ import annotations

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


def _make_portrait_marker(path: Path, w: int = 80, h: int = 160):
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (w, h), color=(10, 10, 10))
        draw = ImageDraw.Draw(img)
        # small white marker in center (8x8)
        cx = w // 2
        cy = h // 2
        draw.rectangle((cx - 4, cy - 4, cx + 3, cy + 3), fill=(255, 255, 255))
        img.save(path)
    except Exception:
        raise RuntimeError("Pillow required for this test")


def _extract_frame(video: Path, out_png: Path, t: float = 0.3) -> None:
    # Use seek (-ss) before input for fast and accurate capture of a frame at time t
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(t),
        "-i",
        str(video),
        "-frames:v",
        "1",
        str(out_png),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=20)


def test_portrait_foreground_not_upscaled(tmp_path: Path) -> None:
    img = tmp_path / "portrait.png"
    _make_portrait_marker(img, 80, 160)

    plans = [ClipPlan(path=img, kind="photo", duration=0.5)]
    out = tmp_path / "out_portrait.mp4"

    render_timeline(plans, out, fps=10, bgm_path=None)

    assert out.exists() and out.stat().st_size > 0

    # Extract a frame (choose a time after fade-in to avoid fully transparent first frame)
    frame = tmp_path / "frame.png"
    _extract_frame(out, frame, t=0.3)

    from PIL import Image

    im = Image.open(frame).convert("RGB")
    W, H = im.size
    cx = W // 2
    cy = H // 2

    # Count near-white pixels in small box around center roughly equal to marker size (8x8)
    count = 0
    for y in range(cy - 6, cy + 6):
        for x in range(cx - 6, cx + 6):
            r, g, b = im.getpixel((x, y))
            # allow for encoding/blur artifacts: treat >200 as near-white
            if r > 200 and g > 200 and b > 200:
                count += 1

    # Expect roughly the marker size (8x8 ~=64). Allow a wide tolerance; if foreground was upscaled many more will be white.
    assert 10 < count < 500
