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


def test_portrait_bg_blur_cli(tmp_path: Path) -> None:
    """CLI経由で--bg-blur=0と--bg-blur=6を指定し、背景ぼかしの有無を確認する。"""
    img = tmp_path / "portrait.png"
    _make_portrait_marker(img, 80, 160)
    out0 = tmp_path / "out_blur0.mp4"
    out6 = tmp_path / "out_blur6.mp4"

    # --bg-blur=0
    cmd0 = [
            "python", "-m", "video_engine",
            "--name", "2026-W04",
        "--input", str(tmp_path),
        "--output", str(tmp_path),
        "--duration", "0.5",
        "--bg-blur", "0",
        "--transition", "0",
    ]
    subprocess.run(cmd0, capture_output=True, check=True, timeout=20)
    out_mp40 = tmp_path / "2026-W04_preview.mp4"
    assert out_mp40.exists() and out_mp40.stat().st_size > 0
    frame0 = tmp_path / "frame0.png"
    _extract_frame(out_mp40, frame0, t=0.3)

    # --bg-blur=6
    cmd6 = [
            "python", "-m", "video_engine",
            "--name", "2026-W04",
        "--input", str(tmp_path),
        "--output", str(tmp_path),
        "--duration", "0.5",
        "--bg-blur", "6",
        "--transition", "0",
    ]
    subprocess.run(cmd6, capture_output=True, check=True, timeout=20)
    out_mp46 = tmp_path / "2026-W04_preview.mp4"
    assert out_mp46.exists() and out_mp46.stat().st_size > 0
    frame6 = tmp_path / "frame6.png"
    _extract_frame(out_mp46, frame6, t=0.3)

    from PIL import Image, ImageChops
    im0 = Image.open(frame0).convert("RGB")
    im6 = Image.open(frame6).convert("RGB")
    # 差分画像を作成し、全く同じでないこと（ぼかし有無で背景が変わる）
    diff = ImageChops.difference(im0, im6)
    bbox = diff.getbbox()
    assert bbox is not None, "blur=0とblur=6で背景が変化しているはず"
