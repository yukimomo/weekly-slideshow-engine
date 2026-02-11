from __future__ import annotations

from pathlib import Path

from video_engine.config import (
    build_config_defaults,
    build_effective_config,
    format_effective_config,
    load_yaml_config,
)


def test_load_yaml_config_resolves_paths(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg = config_dir / "settings.yml"
    cfg.write_text(
        "input: ./media\noutput: ../out\nbgm: bgm\n",
        encoding="utf-8",
    )

    data = load_yaml_config(cfg)

    assert data["input"] == (config_dir / "media").resolve(strict=False)
    assert data["output"] == (config_dir / "../out").resolve(strict=False)
    assert data["bgm"] == (config_dir / "bgm").resolve(strict=False)


def test_config_precedence() -> None:
    base = build_config_defaults()
    config_values = {
        "preset": "mobile",
        "duration": 40.0,
        "bgm_volume": 20.0,
        "scan_all": True,
    }
    cli_values = {
        "preset": "youtube",
        "duration": 55.0,
        "scan_all": False,
    }
    provided = {"preset", "duration"}

    effective = build_effective_config(base, "youtube", config_values, cli_values, provided)

    assert effective["duration"] == 55.0
    assert effective["bgm_volume"] == 20.0
    assert effective["scan_all"] is True
    assert effective["resolution"] == (1920, 1080)


def test_format_effective_config_resolution() -> None:
    effective = build_config_defaults()
    effective["resolution"] = (1920, 1080)
    printable = format_effective_config(effective)
    assert printable["resolution"] == "1920x1080"
