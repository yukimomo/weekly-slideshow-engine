"""End-to-end CLI smoke tests: scan -> timeline -> render.

These are skipped when moviepy or ffmpeg are not available to keep CI
stable. They run the module via `sys.executable -m video_engine` so they
exercise packaging / CLI behavior.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import wave
import math
from pathlib import Path

import pytest
import conftest

pytestmark = [
    pytest.mark.skipif(not conftest.moviepy_usable(), reason="moviepy not usable (partial/misinstalled)"),
    pytest.mark.skipif(not conftest.ffmpeg_available(), reason="ffmpeg not available in PATH"),
]


def _run_module(args: list[str], env_extra: dict | None = None) -> subprocess.CompletedProcess:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"

    env = os.environ.copy()
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_dir) + os.pathsep + prev
    if env_extra:
        env.update(env_extra)

    cmd = [sys.executable, "-m", "video_engine"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)


def test_e2e_cli_creates_preview(tmp_path: Path) -> None:

    # Setup repo-like input
    input_dir = tmp_path / "input"
    date_dir = input_dir / "2026-01-22"
    date_dir.mkdir(parents=True)

    img = date_dir / "img.png"
    img2 = date_dir / "img2.png"
    try:
        from PIL import Image

        im = Image.new("RGB", (32, 32), color="purple")
        im.save(img)
        im2 = Image.new("RGB", (32, 32), color="orange")
        im2.save(img2)
    except Exception:
        img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")
        img2.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")

    # Also add a tiny MP4 to exercise video handling
    v = date_dir / "t.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=160x120:d=0.5",
        "-r",
        "10",
        str(v),
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=10)

    bgm_dir = tmp_path / "bgm"
    bgm_dir.mkdir()
    wav = bgm_dir / "bgm.wav"

    # tiny wave file 0.2s
    freq = 440.0
    rate = 44100
    duration = 0.2
    nframes = int(rate * duration)
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = bytearray()
        for i in range(nframes):
            t = i / rate
            val = int(32767 * 0.2 * math.sin(2 * math.pi * freq * t))
            frames += val.to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))

    out_dir = tmp_path / "output"
    out_dir.mkdir()

    # Run real render for 2 seconds
    proc = _run_module(["--name", "2026-W04", "--scan-all", "--input", str(input_dir), "--bgm", str(bgm_dir), "--output", str(out_dir), "--duration", "2", "--transition", "0.2"])
    assert proc.returncode == 0, f"stdout={proc.stdout!r}\nstderr={proc.stderr!r}"

    expected = out_dir / "2026-W04_preview.mp4"
    assert expected.exists() and expected.stat().st_size > 0


def test_e2e_cli_dry_run(tmp_path: Path) -> None:
    # Dry run should not create files
    input_dir = tmp_path / "input"
    date_dir = input_dir / "2026-01-22"
    date_dir.mkdir(parents=True)

    img = date_dir / "img.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82")

    out_dir = tmp_path / "output"
    out_dir.mkdir()

    proc = _run_module(["--name", "2026-W04", "--scan-all", "--input", str(input_dir), "--bgm", str(tmp_path / "no_bgm"), "--output", str(out_dir), "--duration", "2", "--dry-run"])
    assert proc.returncode == 0
    assert list(out_dir.iterdir()) == []
