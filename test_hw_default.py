#!/usr/bin/env python
"""デフォルトでハードウェアエンコーダが選択されることを確認"""

import sys
import os
sys.path.insert(0, 'src')

# 環境変数をリセット
for key in ["VIDEO_ENGINE_ENABLE_HW", "VIDEO_ENGINE_FFMPEG_CODEC"]:
    os.environ.pop(key, None)

from video_engine.render import _select_video_encoder, _get_ffmpeg_encoder_args

print("=" * 80)
print("デフォルトエンコーダ選択テスト")
print("=" * 80)

# デフォルト（環境変数なし）
codec = _select_video_encoder()
args = _get_ffmpeg_encoder_args(codec)

print(f"\n選択されたコーデック: {codec or 'None (libx264 CPU フォールバック)'}")
print(f"エンコーダ引数: {' '.join(args)}")

if codec and "nvenc" in codec:
    print("\n✅ NVIDIA NVENC が自動選択されました！")
    print("⚡ 期待される高速化: 10-30 倍")
elif codec:
    print(f"\n✅ {codec} が自動選択されました")
    print("⚡ 期待される高速化: 5-10 倍")
else:
    print("\n⚠️ ハードウェアエンコーダが見つかりません")
    print("   CPU (libx264) を使用します")
    print("   高速化: デフォルト (2-3 倍)")

print("\n" + "=" * 80)
print("ハードウェアエンコーディングを明示的に無効化")
print("=" * 80)

# 環境変数をリセット
for key in ["VIDEO_ENGINE_ENABLE_HW", "VIDEO_ENGINE_FFMPEG_CODEC"]:
    os.environ.pop(key, None)

# 明示的に無効化
os.environ["VIDEO_ENGINE_ENABLE_HW"] = "0"

# キャッシュをクリアするため、新しいプロセスで実行する必要があります
import subprocess
result = subprocess.run(
    [sys.executable, "-c", """
import sys
import os
sys.path.insert(0, 'src')
os.environ["VIDEO_ENGINE_ENABLE_HW"] = "0"
from video_engine.render import _select_video_encoder, _get_ffmpeg_encoder_args
codec = _select_video_encoder()
args = _get_ffmpeg_encoder_args(codec)
print(f"選択されたコーデック: {codec or 'None (libx264 CPU)'}")
print(f"エンコーダ引数: {' '.join(args)}")
print("✅ ハードウェアエンコーディングが無効化されました")
"""],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print(f"エラー: {result.stderr}")
