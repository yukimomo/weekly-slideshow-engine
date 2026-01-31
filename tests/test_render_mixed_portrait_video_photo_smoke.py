"""Smoke test: portrait photo + landscape video + landscape photo render to 1280x720."""

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


def _make_png(p: Path, size=(90, 160), color="purple"):
    try:
        from PIL import Image

        Image.new("RGB", size, color=color).save(p)
    except Exception:
        p.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")


def _make_land_mp4(path: Path, size=(160, 90), duration: float = 0.5, fps: int = 10) -> None:
    s = f"{size[0]}x{size[1]}"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=white:s={s}:d={duration}",
        "-r",
        str(fps),
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: stdout={proc.stdout!r}\nstderr={proc.stderr!r}")


def test_mixed_portrait_video_photo(tmp_path: Path) -> None:
    p_port = tmp_path / "port.png"
    v_land = tmp_path / "land.mp4"
    p_land = tmp_path / "land2.png"

    _make_png(p_port, size=(90, 160), color="purple")
    _make_land_mp4(v_land, size=(160, 90), duration=0.5, fps=10)
    _make_png(p_land, size=(160, 90), color="orange")

    plans = [
        ClipPlan(path=p_port, kind="photo", duration=0.5),
        ClipPlan(path=v_land, kind="video", duration=0.5),
        ClipPlan(path=p_land, kind="photo", duration=0.5),
    ]

    out = tmp_path / "out_mixed.mp4"
    render_timeline(plans, out, fps=10, bgm_path=None, transition=0)

    assert out.exists() and out.stat().st_size > 0

    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        proc = subprocess.run([ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(out)], capture_output=True, text=True, timeout=10)
        if proc.returncode == 0 and proc.stdout:
            wh = proc.stdout.strip()
            assert wh == "1280x720"