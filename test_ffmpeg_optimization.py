#!/usr/bin/env python
"""FFmpeg レンダリング高速化テスト"""

import subprocess
import sys
import os
from pathlib import Path

print("=" * 80)
print("FFmpeg レンダリング高速化機能テスト")
print("=" * 80)

# テスト 1: 環境変数なし（デフォルト）
print("\n[テスト1] デフォルト設定 (CPU + libx264 fast preset)")
print("-" * 80)
env = os.environ.copy()
# 環境変数をクリア
env.pop("VIDEO_ENGINE_ENABLE_HW", None)
env.pop("VIDEO_ENGINE_FFMPEG_CODEC", None)
env.pop("VIDEO_ENGINE_FFMPEG_PRESET", None)
env.pop("VIDEO_ENGINE_FFMPEG_CRF", None)

result = subprocess.run(
    [sys.executable, "-c", """
import sys
sys.path.insert(0, 'src')
from video_engine.render import _select_video_encoder, _get_ffmpeg_encoding_preset, _get_ffmpeg_crf, _get_ffmpeg_encoder_args

codec = _select_video_encoder()
preset = _get_ffmpeg_encoding_preset()
crf = _get_ffmpeg_crf()
args = _get_ffmpeg_encoder_args(codec)

print(f"Encoder: {codec or 'libx264 (CPU ベース)'}")
print(f"Preset: {preset}")
print(f"CRF: {crf}")
print(f"Encoder Args: {' '.join(args)}")
"""],
    capture_output=True,
    text=True,
    cwd=str(Path.cwd()),
    env=env
)

print(result.stdout)
if result.stderr:
    print(f"Error: {result.stderr}")

# テスト 2: ハードウェアエンコーディング有効化
print("\n[テスト2] ハードウェアエンコーディング有効化")
print("-" * 80)
env = os.environ.copy()
env["VIDEO_ENGINE_ENABLE_HW"] = "1"

result = subprocess.run(
    [sys.executable, "-c", """
import sys
sys.path.insert(0, 'src')
from video_engine.render import _select_video_encoder, _get_ffmpeg_encoder_args

codec = _select_video_encoder()
args = _get_ffmpeg_encoder_args(codec)

print(f"Encoder: {codec or 'ハードウェアエンコーダが見つかりません'}")
if codec:
    print(f"Encoder Args: {' '.join(args)}")
else:
    print("フォールバック: libx264を使用します")
"""],
    capture_output=True,
    text=True,
    cwd=str(Path.cwd()),
    env=env
)

print(result.stdout)
if result.stderr:
    print(f"Error: {result.stderr}")

# テスト 3: NVIDIA NVENC 明示的指定
print("\n[テスト3] NVIDIA NVENC 明示的指定")
print("-" * 80)
env = os.environ.copy()
env["VIDEO_ENGINE_FFMPEG_CODEC"] = "h264_nvenc"

result = subprocess.run(
    [sys.executable, "-c", """
import sys
sys.path.insert(0, 'src')
from video_engine.render import _select_video_encoder, _get_ffmpeg_encoder_args

codec = _select_video_encoder()
args = _get_ffmpeg_encoder_args(codec)

print(f"Encoder: {codec}")
print(f"Encoder Args: {' '.join(args)}")
print(f"説明: NVIDIA NVENC は高速 (10-30倍)")
"""],
    capture_output=True,
    text=True,
    cwd=str(Path.cwd()),
    env=env
)

print(result.stdout)

# テスト 4: CPU エンコーディングのカスタムプリセット
print("\n[テスト4] CPU エンコーディング: カスタムプリセット")
print("-" * 80)
env = os.environ.copy()
env["VIDEO_ENGINE_FFMPEG_CODEC"] = "libx264"
env["VIDEO_ENGINE_FFMPEG_PRESET"] = "ultrafast"
env["VIDEO_ENGINE_FFMPEG_CRF"] = "32"

result = subprocess.run(
    [sys.executable, "-c", """
import sys
sys.path.insert(0, 'src')
from video_engine.render import _select_video_encoder, _get_ffmpeg_encoding_preset, _get_ffmpeg_crf, _get_ffmpeg_encoder_args

codec = _select_video_encoder()
preset = _get_ffmpeg_encoding_preset()
crf = _get_ffmpeg_crf()
args = _get_ffmpeg_encoder_args(codec)

print(f"Encoder: {codec}")
print(f"Preset: {preset}")
print(f"CRF: {crf}")
print(f"Encoder Args: {' '.join(args)}")
print(f"説明: ultrafast は最速だが低品質、CRF 32 はさらに品質を下げた設定")
"""],
    capture_output=True,
    text=True,
    cwd=str(Path.cwd()),
    env=env
)

print(result.stdout)

print("\n" + "=" * 80)
print("✅ 環境変数による高速化設定テスト完了")
print("=" * 80)
print("""
推奨設定:

【最高速 - NVIDIA GPU がある場合】
$env:VIDEO_ENGINE_ENABLE_HW = "1"
python -m video_engine render 2026-W04

【高速 - Intel/AMD GPU がある場合】
$env:VIDEO_ENGINE_ENABLE_HW = "1"
python -m video_engine render 2026-W04

【CPU のみの場合（最速）】
$env:VIDEO_ENGINE_FFMPEG_CODEC = "libx264"
$env:VIDEO_ENGINE_FFMPEG_PRESET = "ultrafast"
$env:VIDEO_ENGINE_FFMPEG_CRF = "32"
python -m video_engine render 2026-W04

【CPU のみの場合（バランス）】
デフォルトで十分 (fast preset, CRF 28)
python -m video_engine render 2026-W04
""")
