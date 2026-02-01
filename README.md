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
pip install -r requirements.txt
```

---

## 使い方（CLI）

`python -m video_engine` のCLIで入力フォルダ内の写真・動画をスキャンしてプレビュー動画を生成します。主なオプションは以下の通りです。

- `--name <text>`: 出力ファイル名に使う名前（例: 2026-W04）。`--week`は互換エイリアス。
- `--scan-all`: `--input`配下のサブフォルダも含めて再帰的に走査します。未指定時はフォルダ直下のみを走査します。
- `--input <path>`: 入力ディレクトリ（既定: ./input）。
- `--bgm <path>`: BGMファイルまたはディレクトリ（既定: ./bgm）。
- `--output <path>`: 出力ディレクトリ（既定: ./output）。
- `--duration <seconds>`: 目標秒数（既定: 8.0）。
- `--transition <seconds>`: クリップのフェード長（既定: 0.3、0で無効）。
- `--preserve-videos`: 動画の元の長さを優先（時間の扱い）。
- `--bg-blur <float>`: 背景ぼかし半径（既定: 6.0、0で無効）。写真は常に「前景contain＋背景ぼかし」。動画は出力が縦長またはソースが縦動画なら写真同様、横長（出力・ソースとも横）は全面表示（カバー拡大＋中央クロップ）。
- `--resolution <WIDTHxHEIGHT>`: 出力解像度（例: 1920x1080、1080x1920）。目安: 320x240～8192x4320。未指定時は既定を使用。
- `--preset <name>`: プリセット（youtube / mobile / preview）。プリセット適用後に明示フラグが上書き。
- `--dry-run`: 実行せず有効値とスキャン結果を表示（解像度／duration／transition／bg_blur など）。

GPU搭載環境では、利用可能なハードウェアエンコーダ（NVENC / QSV / AMF / VideoToolbox）があれば自動で使用します。
ただし、合成・ぼかし・リサイズ等の処理はMoviePy側のCPU処理が中心です。
強制的にエンコーダを指定したい場合は環境変数 `VIDEO_ENGINE_FFMPEG_CODEC` を設定してください（空文字で無効化）。

例:

```bash
python -m video_engine --week 2026-W04 --input ./input --bgm ./bgm \
  --output ./output --duration 60 --transition 0.3 --bg-blur 8 --resolution 1080x1920
```

プリセット＋ドライラン例:

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

