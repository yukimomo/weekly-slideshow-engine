# weekly-slideshow-engine

A Python-based engine that automatically generates a weekly 1-minute slideshow
video from photos and videos.  
Designed for fully automated, rule-based video composition using MoviePy.
# weekly-slideshow-engine

毎週の写真・動画から自動で1分のスライドショー動画を生成する、Pythonベースのエンジンです。MoviePyを用いたルールベースの自動合成を前提に、手放し運用を目標にしています。

---

## 概要
ローカルディレクトリ（例: OneDrive同期フォルダ）内の写真・動画を取り込み、週次スライドショーを自動生成します。入力ディレクトリにメディアを置くだけで、毎週の映像が一貫したルールで出力されます。

---

## 特徴
- ISO週に基づく週次バッチ生成
- 1分（60秒）の固定出力を想定
- 写真・動画の混在入力に対応
- タイムラインの自動正規化
- 背景音楽（BGM）の統合
- CLIによる完全自動処理
- OneDrive等の同期フォルダ運用を想定

---

## 必要環境
- Python 3.11+
- ffmpeg（PATHに設定されていること）
- OS: Windows / macOS / Linux

写真のEXIF読み取りやHEIC対応を行う場合は、以下を追加で導入してください（任意）:
- Pillow
- pillow-heif（HEIC/HEIF対応）

---

## インストール
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e .
```

requirements.txt を使う場合は以下でもOKです（開発前提の簡易手順）:

```bash
pip install -r requirements.txt
```

---

## 使い方（CLI）

`python -m video_engine` のCLIで入力フォルダ内の写真・動画をスキャンしてプレビュー動画を生成します。主なオプションは以下の通りです。

PowerShell 実行例:

```powershell
video-engine --help
```

- `--name <text>`: 出力ファイル名に使う名前（例: 2026-W04）。`--week`は互換エイリアス。
- `--scan-all`: `--input`配下のサブフォルダも含めて再帰的に走査します。未指定時はフォルダ直下のみを走査します。
- `--verbose-scan` / `--debug-scan`: スキャンの詳細ログを出力します（除外理由の集計、先頭N件のサンプルなど）。
- `--scan-limit <n>`: 詳細ログで表示するサンプル件数（既定: 20、0で非表示）。
- `--input <path>`: 入力ディレクトリ（既定: ./input）。
- `--bgm <path>`: BGMファイルまたはディレクトリ（既定: ./bgm）。
- `--output <path>`: 出力ディレクトリ（既定: ./output）。
- `--duration <seconds>`: 目標秒数（既定: 8.0）。
- `--transition <seconds>`: クリップのフェード長（既定: 0.3、0で無効）。
- `--fade-max-ratio <float>`: フェード長の上限を「クリップ長に対する比率」で指定（既定: 1.0 = 上限なし）。
- `--preserve-videos`: 動画の元の長さを優先（時間の扱い）。
- `--bg-blur <float>`: 背景ぼかし半径（既定: 6.0、0で無効）。0を指定した場合、処理が20-30%高速化します。
  - 背景ぼかし有効（`> 0`）: 写真・動画ともに「前景contain＋背景ぼかし」処理（品質重視）
  - 背景ぼかし無効（`= 0`）: 「全面カバー拡大＋中央クロップ」で処理（高速処理）
- `--bgm-volume <float>`: BGM音量をビデオ音声に対する百分率で指定（既定: 10.0、範囲: 0-200）。
  - 10%: ビデオ音の話声を聞き取りやすいさりげない音量（推奨）
  - 100%: BGMとビデオ音が同じ大きさ
  - 0%: BGM無効（ビデオ音声のみ）
- `--resolution <WIDTHxHEIGHT>`: 出力解像度（例: 1920x1080、1080x1920）。目安: 320x240～8192x4320。未指定時は既定を使用。
- `--preset <name>`: プリセット（youtube / mobile / preview）。プリセット適用後に明示フラグが上書き。
- `--config <path>`: YAMLの設定ファイル。プリセット適用後に読み込み、CLIが上書きします。
- `--print-config`: 最終的な設定（effective config）を出力します。
- `--dry-run`: 実行せず有効値とスキャン結果を表示（サンプル一覧／集計／解像度／duration／transition／bg_blur など）。
- `--fps <int>`: 出力FPS（既定: 30）。
- `--photo-seconds <float>`: 写真1枚あたりの基準秒数（既定: 2.5）。
- `--video-max-seconds <float>`: 動画1本あたりの最大秒数（既定: 5.0）。
- `--photo-max-seconds <float>`: 余剰時間配分時の写真最大秒数（既定: 6.0）。

### プリセットの主要項目

| Preset | Duration | Resolution | Transition | bg_blur | bgm_volume | FPS |
| --- | --- | --- | --- | --- | --- | --- |
| youtube | 60s | 1920x1080 | 0.3s | 6.0 | 10% | 30 |
| mobile | 60s | 1080x1920 | 0.25s | 8.0 | 10% | 30 |
| preview | 8s | 1280x720 | 0.2s | 4.0 | 10% | 30 |

### 設定ファイル（YAML）

優先順位:

1. preset既定
2. configファイル
3. CLI引数

相対パスはconfigファイルの場所基準で解決されます。

例:

```yaml
preset: youtube
name: 2026-W04
input: ./input
output: ./output
bgm: ./bgm
resolution: 1920x1080
fps: 30
duration: 60
photo_seconds: 2.5
video_max_seconds: 5.0
photo_max_seconds: 6.0
transition: 0.3
fade_max_ratio: 1.0
bg_blur: 6.0
bgm_volume: 10.0
scan_all: false
preserve_videos: false
```

### ハードウェアエンコーディング（自動最適化）

GPU搭載環境では、利用可能なハードウェアエンコーダが自動で検出・使用されます：

- **NVIDIA NVENC** (`h264_nvenc`): 10-30倍の高速化
- **Intel QuickSync** (`h264_qsv`): 5-10倍の高速化  
- **AMD VCE** (`h264_amf`): 5-10倍の高速化
- **Apple VideoToolbox** (`h264_videotoolbox`): GPU対応Mac
- **CPU Fallback** (`libx264`): GPU未搭載環境での標準処理

環境変数で制御可能：

```bash
# ハードウェアエンコーディングを強制無効（CPU処理）
set VIDEO_ENGINE_FFMPEG_CODEC=
python -m video_engine --week 2026-W04 ...

# 特定のエンコーダを指定
set VIDEO_ENGINE_FFMPEG_CODEC=libx264
python -m video_engine --week 2026-W04 ...

# エンコーディングプリセット（ultrafast/superfast/veryfast/faster/fast/medium）
set VIDEO_ENGINE_FFMPEG_PRESET=superfast
python -m video_engine --week 2026-W04 ...

# CRF品質（0-51、低いほど高品質、デフォルト28）
set VIDEO_ENGINE_FFMPEG_CRF=23
python -m video_engine --week 2026-W04 ...
```

### BGM音声ミックス最適化

BGM音量は FFmpeg の `amix` フィルタで複数の音声トラックをミックスします：

1. **音量制御**: `--bgm-volume <percent>` でBGMの音量を調整
  - ビデオ内の音声が聞き取りやすい10%がデフォルト
  - 100% で BGM とビデオ音が同じ大きさ
   
2. **フェード処理**: BGMの開始・終了時にフェードイン/アウト
   - `fade_in` / `fade_out` パラメータで制御

3. **AAC エンコーディング**: `-q:a 8` で高品質オーディオを保証

例:

```bash
python -m video_engine --week 2026-W04 --input ./input --bgm ./bgm \
  --output ./output --duration 60 --transition 0.3 --bg-blur 8 --bgm-volume 10 --resolution 1080x1920
```

スキャン診断の例:

```bash
python -m video_engine --week 2026-W04 --input ./input --dry-run --verbose-scan --scan-limit 20
```

設定ファイルの例:

```bash
python -m video_engine --config settings.sample.yml --print-config
```

プリセット＋ドライラン例（実効値の確認）:

```bash
python -m video_engine --week 2026-W04 --input ./input --output ./output \
  --preset mobile --dry-run --resolution 1080x1920
```

---

## レンダリングの簡易テスト（smoke）

一部のスモーク／E2Eテストでは、MoviePyと`ffmpeg`が正しく動作する環境が必要です。

要件:
- Python 3.11+
- `ffmpeg` が `PATH` にあること
- MoviePy の `render` エクストラをインストール

推奨セットアップ（MoviePy等のレンダー依存関係をまとめて導入）:

```bash
pip install -e ".[render]"
```

テスト実行:

```bash
# 高速テスト（23個、約1秒）
python -m pytest tests/ -m "not slow" -q

# すべてのテスト（レンダリングを含む、10-20分）
python -m pytest tests/ -q

# 特定のテストのみ実行
python -m pytest tests/test_scan.py tests/test_timeline.py -v
```

### テストマーカー

- `@pytest.mark.slow`: レンダリング処理を含む遅いテスト（30秒以上）
- `@pytest.mark.render`: FFmpeg/MoviePy関連のレンダリングテスト

`-m "not slow"` を指定すると高速なユニットテスト（23個）のみが実行され、約1秒で完了します。

---

## パフォーマンス最適化

### 自動最適化機能

1. **ハードウェアエンコーディング**: NVIDIA/Intel/AMD のGPUエンコーダが自動検出・使用されます（10-30倍高速化）
2. **FFmpeg コマンド最適化**:
   - **Concat処理**: `-protocol_whitelist file,pipe -max_muxing_queue_size 1024 -fflags +genpts`
   - **BGM混音**: 明示的なストリーム指定 `-map 0:v:0 -map 1:a:0` + AAC品質最適化 `-q:a 8`
   - **MP4最適化**: `-movflags "+faststart+empty_moov"` で高速なメタデータ生成
3. **フィルタ処理最適化**: `--bg-blur 0` を指定すると、背景ぼかスキップで20-30%高速化

### 予想処理時間（1分動画生成、1080p）

| 環境 | 画像のみ | 画像+動画混合 | 推奨用途 |
|------|---------|-------------|----------|
| NVIDIA NVENC | 30-45秒 | 45-60秒 | 高速生成 |
| Intel QSV | 45-90秒 | 60-120秒 | ノートパソコン |
| AMD VCE | 45-90秒 | 60-120秒 | AMD GPU搭載 |
| CPU (libx264) | 3-5分 | 4-8分 | GPU未搭載 |

---

## 入力スキャンの挙動（今回の修正）
- **日付ディレクトリ優先**: `input/YYYY-MM-DD/` 形式のサブディレクトリをISO週範囲で走査し、写真（`.jpg/.jpeg/.png`）と動画（`.mp4/.mov`）を収集します。写真はEXIF日時を優先、無い場合はファイル更新時刻を使用します。
- **平置きフォールバック**: 週範囲に該当する日付サブディレクトリが存在せず、`--input`直下にメディアが平置きされている場合は、直下のファイルを拡張子で判定して収集します（テストや簡易利用向けのフォールバック）。

---

## 解像度と動画保持のルール（今回の修正）
- **既定解像度**: 明示指定が無い場合は既定 `1280x720` を使用します。
- **`--preserve-videos`**: 解像度未指定かつこのフラグが有効のとき、入力動画群の中で最大のフレームサイズからキャンバスを自動決定します。
- **前景のスケーリング**:
  - 写真は常に`contain`で中央配置、空白は背景の`cover`＋ぼかしで満たします。
  - 動画は出力が横長のときは**カバー拡大＋中央クロップ**で全面表示（背景は使いません）。出力が縦長（例: mobile）では**写真と同じ**く`contain`で中央配置し、空白は背景の`cover`＋ぼかしで満たします。
    - 動画は以下のルールで処理します:
      - **縦長出力（例: mobile）またはソースが縦動画**: 写真と同様に`contain`で中央配置し、空白は背景の`cover`＋ぼかしで満たします。
      - **横長出力かつソースも横**: **カバー拡大＋中央クロップ**で全面表示（背景は使いません）。
- **背景の生成**: 背景は`cover`相当のスケーリング＋中央クロップでキャンバスを満たし、`--bg-blur`の半径でガウスぼかし（`0`で無効）。

---

## 仮想環境の自動再実行（今回の修正）
- `python -m video_engine`起動時に、このPythonから`moviepy`が見つからない場合は、以下の順で仮想環境のPythonを探索して自動再実行します。
  - 環境変数`VIRTUAL_ENV`配下の `Scripts/python.exe`（Windows）または `bin/python`（Unix系）。
  - プロジェクト直下の`.venv/Scripts/python.exe`（Windows）または `.venv/bin/python`（Unix系）。
- これにより、テストや開発時に仮想環境へ自動で切り替わり、依存関係（MoviePy等）が確実に解決されます。必要に応じて仮想環境の有効化または`.venv`の作成を行ってください。

