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
