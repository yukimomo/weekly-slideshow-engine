"""Smoke test for rendering with BGM using MoviePy and ffmpeg.

This test is skipped when moviepy or ffmpeg are not available to keep CI
and local runs fast and robust.
"""

from __future__ import annotations

import shutil
import wave
import math
from pathlib import Path
import sys

import pytest

from video_engine.render import render_single_photo


@pytest.mark.slow
@pytest.mark.render
@pytest.mark.skipif(__import__("importlib").util.find_spec("moviepy") is None, reason="moviepy not installed")
def test_render_with_bgm_smoke(tmp_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available in PATH")

    img = tmp_path / "img.png"

    # Create a small PNG via Pillow if available, otherwise write a minimal PNG
    try:
        from PIL import Image

        im = Image.new("RGB", (16, 16), color="green")
        im.save(img)
    except Exception:
        img.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    # Create a short WAV audio of 0.2s mono 44100Hz sine-ish wave
    wav = tmp_path / "bgm.wav"
    freq = 440.0
    rate = 44100
    duration = 0.2
    nframes = int(rate * duration)

    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        frames = bytearray()
        for i in range(nframes):
            t = i / rate
            # simple sine wave amplitude
            val = int(32767 * 0.2 * math.sin(2 * math.pi * freq * t))
            frames += val.to_bytes(2, "little", signed=True)
        w.writeframes(bytes(frames))

    out = tmp_path / "out_bgm.mp4"

    # Use short duration to keep test quick
    render_single_photo(img, out, duration=1.0, fps=10, bgm_path=wav, fade_in=0.1, fade_out=0.1)

    assert out.exists()
    assert out.stat().st_size > 0

    # Optionally verify audio stream exists with ffprobe
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        pytest.skip("ffprobe not available to verify audio stream")

    import subprocess

    proc = subprocess.run([ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "audio" in proc.stdout.lower()
