"""Smoke tests for the `video_engine` CLI.

These tests use `sys.executable -m video_engine` so they exercise the real
module entry point. To allow running without installing the package, the
`PYTHONPATH` used for the subprocess includes the repository's `src/` dir
so the `video_engine` module can be found using the src-layout.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from video_engine import cli


def _run_module(args: list[str]) -> subprocess.CompletedProcess:
    """Run the current Python interpreter with `-m video_engine` plus args.

    Ensures `src/` is on PYTHONPATH so tests work without installing the
    package (compatible with Windows).
    """
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"

    env = os.environ.copy()
    prev = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(src_dir) + os.pathsep + prev

    cmd = [sys.executable, "-m", "video_engine"] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)


def test_help_shows_usage_or_description() -> None:
    proc = _run_module(["--help"])
    assert proc.returncode == 0, f"Help exited non-zero. stdout={proc.stdout!r} stderr={proc.stderr!r}"

    combined = (proc.stdout or "") + (proc.stderr or "")
    assert (
        "Weekly slideshow engine" in combined or combined.lstrip().startswith("usage:")
    ), f"Help output did not contain expected text. stdout={proc.stdout!r} stderr={proc.stderr!r}"


def test_no_args_requires_week() -> None:
    proc = _run_module([])
    # CLI now requires --name on empty invocation; verify it fails with a useful message.
    assert proc.returncode != 0, f"Expected non-zero exit when --name missing. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    assert "argument --name is required" in (proc.stderr or ""), f"stderr did not mention missing --name. stderr={proc.stderr!r}"


def test_cli_entrypoint_accepts_help() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0


def test_cli_accepts_timeline_options(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    rc = cli.main(
        [
            "--dry-run",
            "--input",
            str(input_dir),
            "--timeline-mode",
            "weighted",
            "--video-weight",
            "3",
            "--print-config",
        ]
    )
    assert rc == 0