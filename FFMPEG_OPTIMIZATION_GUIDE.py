#!/usr/bin/env python
"""
FFmpeg レンダリング高速化ガイド

現在の実装:
- ハードウェアエンコーディング対応済み（NVENC, QSV, AMF）
- CPU ベースエンコーディング（libx264）もサポート

高速化方法:
"""

import subprocess
import sys
import os
import shutil

print("=" * 80)
print("FFmpeg レンダリング高速化ガイド")
print("=" * 80)

# 1. 利用可能なエンコーダを確認
print("\n[1] 利用可能なビデオエンコーダを確認")
print("-" * 80)

ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    print("❌ ffmpeg が PATH に見つかりません")
    sys.exit(1)

try:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False
    )
    
    encoders_text = result.stdout or ""
    encoders = encoders_text.splitlines()
    
    # ハードウェアエンコーダをチェック
    hw_encoders = []
    sw_encoders = []
    
    for line in encoders:
        if "h264_nvenc" in line:
            hw_encoders.append("NVIDIA NVENC (h264_nvenc) - 最高速")
        elif "h264_qsv" in line:
            hw_encoders.append("Intel QuickSync (h264_qsv) - 高速")
        elif "h264_amf" in line:
            hw_encoders.append("AMD VCE (h264_amf) - 高速")
        elif "h264_videotoolbox" in line:
            hw_encoders.append("Apple VideoToolbox (h264_videotoolbox) - 高速")
        elif "libx264" in line:
            sw_encoders.append("libx264 - CPU ベース (遅い)")
    
    print("\n✅ ハードウェアエンコーダ:")
    if hw_encoders:
        for enc in hw_encoders:
            print(f"  ✓ {enc}")
    else:
        print("  ✗ ハードウェアエンコーダが見つかりません")
    
    print("\n✅ ソフトウェアエンコーダ:")
    for enc in sw_encoders:
        print(f"  ✓ {enc}")
        
except Exception as e:
    print(f"❌ エンコーダの確認に失敗: {e}")

# 2. 推奨する高速化方法
print("\n" + "=" * 80)
print("[2] 推奨される高速化方法")
print("=" * 80)

print("""
【方法1】ハードウェアエンコーディング有効化 (推奨)
--------------------------------------------------
環境変数を設定してハードウェアエンコーダを有効化:

  Windows (PowerShell):
  $env:VIDEO_ENGINE_ENABLE_HW = "1"
  python -m video_engine render 2026-W04

  Linux/macOS:
  export VIDEO_ENGINE_ENABLE_HW=1
  python -m video_engine render 2026-W04

期待される改善:
  - libx264: 約 3-5 分
  - ハードウェア: 約 30-60 秒 (10倍高速化)

GPU:
  - NVIDIA: h264_nvenc (最高速 - 最新 GPU では 4K でも数秒)
  - Intel: h264_qsv (高速)
  - AMD: h264_amf (高速)
  - Apple: h264_videotoolbox (高速)


【方法2】特定のエンコーダを指定
--------------------------------------------------
特定のエンコーダを強制的に使用:

  Windows:
  $env:VIDEO_ENGINE_FFMPEG_CODEC = "h264_nvenc"
  python -m video_engine render 2026-W04

  Linux:
  export VIDEO_ENGINE_FFMPEG_CODEC=h264_nvenc
  python -m video_engine render 2026-W04

利用可能なエンコーダ:
  - h264_nvenc (NVIDIA)
  - h264_qsv (Intel)
  - h264_amf (AMD)
  - h264_videotoolbox (Apple)
  - libx264 (CPU - デフォルト)


【方法3】ビットレート設定の最適化 (今後の改善)
--------------------------------------------------
コア処理で ffmpeg コマンドに以下を追加可能:

  - ビットレート制御: -crf 28-32 (品質/速度のトレードオフ)
  - プリセット: -preset fast (libx264)
  - 詳細フレーム: -g 60 (キーフレーム間隔)

例: libx264 で高速化
  -c:v libx264 -crf 28 -preset fast

例: NVIDIA NVENC
  -c:v h264_nvenc -rc vbr -cq 23


【方法4】並列処理 (今後の改善)
--------------------------------------------------
複数のクリップを並列処理することで全体時間を短縮:

  - 現在: 各クリップを順序立てて処理
  - 改善: 複数クリップを同時処理（リソースが許す範囲で）


【方法5】キャッシング (今後の改善)
--------------------------------------------------
同じ入力ファイルに対する処理結果をキャッシュ
""")

print("\n" + "=" * 80)
print("[3] 現在のコード設定")
print("=" * 80)
print("""
ffmpeg コマンド例:

写真からのビデオ生成:
  ffmpeg -y -loop 1 -i input.jpg -t 3.0 -r 30 -filter_complex ... \\
    -c:v libx264 -pix_fmt yuv420p -profile:v main -level 4.1 \\
    output.mp4

ビデオクリップの処理:
  ffmpeg -y -i input.mp4 -t 3.0 -r 30 -filter_complex ... \\
    -c:v libx264 -pix_fmt yuv420p -profile:v main -level 4.1 \\
    output.mp4

クリップの結合:
  ffmpeg -f concat -i list.txt -c copy output.mp4

BGM ミックス:
  ffmpeg -i video.mp4 -stream_loop -1 -i bgm.mp3 \\
    -c:v copy -c:a aac output.mp4
""")

print("\n" + "=" * 80)
print("[4] パフォーマンス比較")
print("=" * 80)
print("""
1 分のビデオ生成（60秒、1280x720, 30fps）にかかる時間:

            ビットレート    エンコード時間    相対速度
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
libx264     ~2000 kbps      ~3-5 分           1x
libx264 fast ~2000 kbps     ~1-2 分           2-3x
h264_qsv    ~2000 kbps      ~30-60 秒         5-10x
h264_nvenc  ~2000 kbps      ~10-30 秒         10-30x
h264_amf    ~2000 kbps      ~30-60 秒         5-10x
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

注: 実際の時間は GPU/CPU 性能に大きく依存します
""")

print("\n" + "=" * 80)
print("✅ 利用可能なハードウェアエンコーダをチェックして、")
print("   VIDEO_ENGINE_ENABLE_HW=1 で有効化することをお勧めします！")
print("=" * 80)
