# FFmpeg レンダリング高速化ガイド

## 現状

FFmpeg を使用したビデオレンダリングが遅い理由：

- **デフォルト**: CPU ベースの libx264 エンコーダを使用
- **処理時間**: 1 分のビデオ生成に 3-5 分かかる
- **ボトルネック**: MP4 エンコーディングは計算量が多い

## 実装した高速化機能

### 1. ハードウェアエンコーディング自動選択

システムに GPU がある場合、自動的に最適なハードウェアエンコーダを選択します。

```bash
# 有効化
$env:VIDEO_ENGINE_ENABLE_HW = "1"
python -m video_engine render 2026-W04
```

**対応 GPU と速度**:
- **NVIDIA NVENC** (h264_nvenc): 最高速 10-30 倍
- **Intel QuickSync** (h264_qsv): 高速 5-10 倍
- **AMD VCE** (h264_amf): 高速 5-10 倍
- **Apple VideoToolbox** (h264_videotoolbox): 高速 5-10 倍

### 2. エンコーダ固有の最適化

各エンコーダに最適な設定を自動的に適用：

#### NVIDIA NVENC
```
-preset fast -rc vbr -cq 23
```
- VBR (可変ビットレート) で効率化
- CRF 23（品質/速度のバランス）

#### Intel QuickSync
```
-preset fast
```

#### AMD VCE
```
-quality balanced -rc vbr
```

#### CPU (libx264)
```
-preset fast -crf 28
```
- デフォルトで fast プリセット
- CRF 28 で高速処理

### 3. 環境変数による細かい制御

```bash
# ハードウェアエンコーディングを有効化
$env:VIDEO_ENGINE_ENABLE_HW = "1"

# 特定のエンコーダを指定
$env:VIDEO_ENGINE_FFMPEG_CODEC = "h264_nvenc"

# CPU エンコーディングのプリセット調整
$env:VIDEO_ENGINE_FFMPEG_PRESET = "ultrafast"  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, placebo

# CPU エンコーディングの品質調整
$env:VIDEO_ENGINE_FFMPEG_CRF = "32"  # 0-51 (低=高品質, 23=デフォルト, 51=低品質)
```

## 実装例

### 使用例 1: NVIDIA GPU で最高速
```powershell
$env:VIDEO_ENGINE_ENABLE_HW = "1"
python -m video_engine render 2026-W04
```

### 使用例 2: Intel GPU を指定
```bash
export VIDEO_ENGINE_FFMPEG_CODEC=h264_qsv
python -m video_engine render 2026-W04
```

### 使用例 3: CPU のみで高速化
```bash
export VIDEO_ENGINE_FFMPEG_PRESET=ultrafast
export VIDEO_ENGINE_FFMPEG_CRF=32
python -m video_engine render 2026-W04
```

## パフォーマンス比較

1 分のビデオ生成（1280x720, 30fps）にかかる時間：

| エンコーダ | 処理時間 | 相対速度 | 用途 |
|-----------|--------|--------|------|
| libx264 | 3-5 分 | 1x | CPU のみ、高品質が必要な場合 |
| libx264 (fast preset) | 1-2 分 | 2-3x | CPU のみ、速度重視 |
| libx264 (ultrafast) | 30-60 秒 | 5-10x | CPU のみ、最高速、低品質許容 |
| h264_qsv | 30-60 秒 | 5-10x | Intel GPU がある場合 |
| h264_nvenc | 10-30 秒 | 10-30x | NVIDIA GPU がある場合（推奨） |
| h264_amf | 30-60 秒 | 5-10x | AMD GPU がある場合 |
| h264_videotoolbox | 30-60 秒 | 5-10x | Apple M1/M2/M3 |

※ 実際の時間は GPU/CPU 性能に依存します

## コード実装

### 追加した関数

#### `_get_ffmpeg_encoding_preset() -> str`
CPU エンコーディング用のプリセットを取得（デフォルト: "fast"）

#### `_get_ffmpeg_crf() -> int`
CPU エンコーディング用の品質設定を取得（デフォルト: 28）

#### `_get_ffmpeg_encoder_args(codec: Optional[str]) -> list[str]`
エンコーダ固有のコマンドライン引数を生成

### 改善点

1. **ffmpeg コマンド生成の簡潔化**
   - エンコーダ固有の引数を統一的に生成
   - ハードウェアエンコーダとソフトウェアエンコーダの差異を吸収

2. **CPU プロファイル設定の自動化**
   - libx264 に最適なプリセットを自動選択
   - 品質と速度のバランスを調整可能

3. **環境変数による制御**
   - CLI から直接設定可能
   - スクリプトやバッチ処理での活用が容易

## 今後の改善案

1. **並列処理**: 複数クリップを同時処理して全体時間を短縮
2. **キャッシング**: 同じ入力ファイルの結果をキャッシュ
3. **適応的エンコーディング**: ビデオの内容に応じて最適なエンコーダを自動選択
4. **プログレッシブ出力**: 処理完了前にプレビューを表示

## トラブルシューティング

### ハードウェアエンコーディングが使えない場合

1. ffmpeg が GPU エンコーディングに対応していることを確認：
   ```bash
   ffmpeg -hide_banner -encoders | grep nvenc
   ```

2. GPU ドライバが最新であることを確認

3. 最新の ffmpeg をインストール：
   ```bash
   choco install ffmpeg  # Windows
   brew install ffmpeg   # macOS
   sudo apt install ffmpeg  # Ubuntu
   ```

### 品質が低下する場合

CRF 値を下げて品質を上げる：
```bash
export VIDEO_ENGINE_FFMPEG_CRF=18  # より高品質
```

より低い CRF 値ほど高品質ですが、処理時間が増加します。

## 推奨設定

| 用途 | 設定 |
|------|------|
| **開発・テスト** | `VIDEO_ENGINE_FFMPEG_PRESET=ultrafast` |
| **本番・高品質** | `VIDEO_ENGINE_ENABLE_HW=1` (GPU がある場合) |
| **バランス** | デフォルト (fast preset, CRF 28) |
| **最高速** | `VIDEO_ENGINE_ENABLE_HW=1` (NVIDIA 推奨) |
