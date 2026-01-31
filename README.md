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

`python -m video_engine` のCLIでISO週を指定してプレビュー動画を生成します。主なオプションは以下の通りです。

- `--week <ISO>`: ISO週を指定（例: `2026-W04`）。必須。
- `--input <path>`: 入力ディレクトリ（既定: `./input`）。
- `--bgm <path>`: BGMファイルまたはディレクトリ（既定: `./bgm`）。
- `--output <path>`: 出力ディレクトリ（既定: `./output`）。
- `--duration <seconds>`: プレビュー動画の目標秒数（既定: `8.0`）。
- `--transition <seconds>`: クリップごとのフェードイン/フェードアウト長（既定: `0.3`、`0`で無効）。
- `--preserve-videos`: 有効にすると動画の元ファイルの長さ（duration）を優先して使用し、可能な範囲でトリミングを最小限にします。描画は「前景contain＋背景ぼかし」の統一方式で行われます。
- `--bg-blur <float>`: 背景レイヤーに適用するぼかし半径（既定: `6.0`、`0`で無効）。写真・動画ともに背景レイヤーへ適用され、前景は常に中央に配置されます（前景はcontainスケールで全面が見えるように調整）。例: `--bg-blur 0`でぼかし無し、`--bg-blur 12`で強いぼかし。
- `--resolution <WIDTHxHEIGHT>`: 出力解像度を `WIDTHxHEIGHT` 形式で指定（例: `1920x1080`、`1080x1920`）。サポート範囲の目安は `320x240` ～ `8192x4320`。未指定時はエンジン既定の解像度を使用します。

例:

```bash
python -m video_engine --week 2026-W04 --input ./input --bgm ./bgm \
  --output ./output --duration 60 --transition 0.3 --bg-blur 8 --resolution 1080x1920
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

