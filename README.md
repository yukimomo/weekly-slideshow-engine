# weekly-slideshow-engine

A Python-based engine that automatically generates a weekly 1-minute slideshow
video from photos and videos.  
Designed for fully automated, rule-based video composition using MoviePy.

---

## Overview
This project provides a rule-driven video generation engine that composes
a weekly slideshow video from photos and videos stored in a local directory
(e.g. OneDrive-synced folders).

The primary goal is **hands-free video creation**:
once media files are placed in the input directory, the engine generates
a consistent, ready-to-watch weekly video without manual editing.

---

## Features
- Weekly batch video generation (ISO week-based)
- Fixed 60-second output
- Mixed photo and video input
- Automatic timeline normalization
- Background music integration
- Fully automated CLI execution
- Designed for OneDrive-synced folders

---

## Requirements
- Python 3.11+
- ffmpeg (must be available in PATH)
- OS: Windows / macOS / Linux

---

## Installation
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## CLI usage

The project provides a small CLI wrapper (`python -m video_engine`) that
builds and renders a short preview video for an ISO week. Common options:

- `--week <ISO>`: ISO week string, e.g. `2026-W04` (required)
- `--input <path>`: input directory (default `./input`)
- `--bgm <path>`: BGM file or directory (default `./bgm`)
- `--output <path>`: output directory (default `./output`)
- `--duration <seconds>`: target preview duration in seconds (default `8.0`)
- `--transition <seconds>`: per-clip fade-in/out length (default `0.3`)
- `--preserve-videos`: when set, video files are included at their native
  resolution and (when multiple videos exist) the canvas size is chosen as
  the maximum width/height among the videos. Videos will be centered on the
  canvas and not rescaled; photos are fit to the canvas.
- `--dry-run`: show what would be done without creating output files

Example:

```bash
python -m video_engine --week 2026-W04 --input ./input --bgm ./bgm \
  --output ./output --duration 60 --transition 0.3 --preserve-videos
```

## Running render smoke tests

Some smoke and end-to-end tests require a fully usable MoviePy installation and `ffmpeg` on `PATH`.

Requirements:
- Python 3.11+
- `ffmpeg` available in `PATH`
- MoviePy installed with the `render` extras

Recommended setup (installs MoviePy and other render dependencies):

```bash
pip install -e ".[render]"
```
