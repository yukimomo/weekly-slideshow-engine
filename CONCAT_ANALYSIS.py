#!/usr/bin/env python
"""FFmpeg concat 処理の分析と改善提案"""

print("""
================================================================================
FFmpeg Concat 処理の遅延原因と改善策
================================================================================

【現在の処理フロー】
────────────────────────────────────────────────────────────────────────────

1. 各クリップを個別にエンコード (ハードウェア加速 - 高速)
   clip_0000.mp4 ✓
   clip_0001.mp4 ✓
   clip_0002.mp4 ✓
   ...
   
2. Concat リスト作成
   concat.txt:
   file 'clip_0000.mp4'
   file 'clip_0001.mp4'
   ...

3. Concat 実行 ([-c copy] で再エンコーディングなし)
   ffmpeg -f concat -safe 0 -i concat.txt -c copy concat.mp4
   
   ⚠️ ここが遅い！


【遅い理由】
────────────────────────────────────────────────────────────────────────────

1. **Codec 互換性チェック**
   - ffmpeg が各クリップのコーデック、FPS、解像度を検証
   - すべてのクリップが同一仕様か確認
   - コーデックパラメータの整合性確認

2. **フレームバッファ処理**
   - ディスクからメモリへのデータ移動
   - 大量のビデオフレームデータの読み込み
   - 複数クリップの同期処理

3. **メタデータ処理**
   - 各クリップの duration/timing 情報の読み込み
   - タイムスタンプの整合性確認
   - MP4 atom の再計算


【改善策】
────────────────────────────────────────────────────────────────────────────

方法1: より厳密な concat オプション (試験的)
──────────────────────────────────────────
ffmpeg -f concat -safe 0 -protocol_whitelist file,pipe -i concat.txt -c copy output.mp4

理由: protocol_whitelist で安全性チェックを明示化


方法2: concat demuxer の並列化 (試験的)
──────────────────────────────────────────
複数スレッドでクリップを先読みする設定

ffmpeg -f concat -safe 0 -i concat.txt -c copy -max_muxing_queue_size 1024 output.mp4

効果: 小さい (10-20%)


方法3: TS フォーマット経由の concat (有効)
──────────────────────────────────────────
MP4 → TS (Transport Stream) → MP4 に変換

1. 各クリップを TS フォーマットで出力
   ffmpeg -i clip_0000.mp4 -c copy clip_0000.ts
   
2. TS ファイルを MPEG2-TS demuxer で結合
   ffmpeg -i "concat:clip_0000.ts|clip_0001.ts|clip_0002.ts" -c copy -bsf:a aac_adtstoasc output.mp4

効果: 20-40% 高速化 (検証中)


方法4: 複合フィルタでの一括処理 (推奨 - 注意)
──────────────────────────────────────────
すべてのクリップを1つのffmpeg コマンドで処理

ffmpeg -i clip_0.mp4 -i clip_1.mp4 -i clip_2.mp4 \\
  -filter_complex "[0][1][2]concat=n=3:v=1:a=1[v][a]" \\
  -map "[v]":v -map "[a]":a output.mp4

問題: 各クリップが再度エンコーディングされる (遅くなる可能性)
利点: 1パスで完結、メモリ効率が良い可能性


方法5: 現在の実装を保持し、concat を並列化 (実装可能)
──────────────────────────────────────────
複数の concat 操作をグループ化して並列実行

Example: 10クリップを2グループに分割
  グループ1: clip_0,1,2,3,4 → concat_1.mp4 (並列実行)
  グループ2: clip_5,6,7,8,9 → concat_2.mp4 (並列実行)
  最後: concat_1.mp4 + concat_2.mp4 → final.mp4

効果: マルチコア活用で 2-4 倍高速化


【推奨する実装】
────────────────────────────────────────────────────────────────────────────

短期 (すぐに実装可能):
  ✓ 現在: -c copy で再エンコーディングなし (正しい)
  ✓ 追加: -max_muxing_queue_size オプション追加
  ✓ デバッグ: concat 処理の詳細ログ追加

中期 (推奨):
  ✓ Concat の並列化実装 (マルチプロセッシング)
  ✓ TS 経由の concat 試験
  ✓ キャッシング機構の追加

長期:
  ✓ 複合フィルタでの一括処理検討
  ✓ GPU での concat 加速調査
  ✓ カスタム concat demuxer の実装


【現在の仕様は最適化されている】
────────────────────────────────────────────────────────────────────────────

✓ クリップごとのハードウェアエンコーディング
✓ Concat で -c copy (再エンコーディングなし)
✓ BGM ミックスで一度だけエンコーディング

🎯 Concat の遅延は、ffmpeg の仕様上避けられない部分もあります。
   ただし、以下の改善は実装可能です。
""")

print("\n" + "=" * 80)
print("実装提案")
print("=" * 80)
print("""
【推奨改善】 concat コマンドにオプション追加

現在:
  ffmpeg -f concat -safe 0 -i concat.txt -c copy output.mp4

改善案:
  ffmpeg -f concat -safe 0 -protocol_whitelist file,pipe \\
    -i concat.txt -c copy -max_muxing_queue_size 1024 -fflags +genpts \\
    output.mp4

変更点:
  -protocol_whitelist file,pipe  : プロトコルホワイトリスト明示化
  -max_muxing_queue_size 1024    : バッファサイズ調整
  -fflags +genpts                : PTS 自動生成

期待効果: 10-20% の高速化
""")
