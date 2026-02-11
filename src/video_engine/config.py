from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from .presets import DEFAULTS, merge_preset

_RESOLUTION_RE = re.compile(r"^(\d{2,5})x(\d{2,5})$")

CONFIG_KEYS = {
    "preset",
    "name",
    "input",
    "output",
    "bgm",
    "resolution",
    "fps",
    "bg_blur",
    "transition",
    "fade_max_ratio",
    "duration",
    "photo_seconds",
    "video_max_seconds",
    "photo_max_seconds",
    "bgm_volume",
    "scan_all",
    "preserve_videos",
}

PATH_KEYS = {"input", "output", "bgm"}

CONFIG_PRINT_ORDER = [
    "preset",
    "name",
    "input",
    "output",
    "bgm",
    "resolution",
    "fps",
    "duration",
    "photo_seconds",
    "video_max_seconds",
    "photo_max_seconds",
    "transition",
    "fade_max_ratio",
    "bg_blur",
    "bgm_volume",
    "scan_all",
    "preserve_videos",
]


def build_config_defaults() -> Dict[str, Any]:
    return {
        "preset": None,
        "name": None,
        "input": Path("./input"),
        "output": Path("./output"),
        "bgm": Path("./bgm"),
        "resolution": DEFAULTS["resolution"],
        "fps": DEFAULTS["fps"],
        "duration": DEFAULTS["duration"],
        "photo_seconds": DEFAULTS["photo_seconds"],
        "video_max_seconds": DEFAULTS["video_max_seconds"],
        "photo_max_seconds": DEFAULTS["photo_max_seconds"],
        "transition": DEFAULTS["transition"],
        "fade_max_ratio": DEFAULTS["fade_max_ratio"],
        "bg_blur": DEFAULTS["bg_blur"],
        "bgm_volume": DEFAULTS["bgm_volume"],
        "scan_all": False,
        "preserve_videos": False,
    }


def load_yaml_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return normalize_config(data, path)


def normalize_config(raw: Dict[str, Any], config_path: Path) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    base_dir = config_path.parent

    for key, value in raw.items():
        if not isinstance(key, str):
            raise ValueError("Config keys must be strings")
        norm_key = key.strip().lower().replace("-", "_")
        if norm_key not in CONFIG_KEYS:
            raise ValueError(f"Unknown config key: {key}")

        if norm_key in PATH_KEYS:
            if value is None:
                normalized[norm_key] = None
                continue
            if not isinstance(value, str):
                raise ValueError(f"Config key {key} must be a string path")
            resolved = _resolve_path(Path(value), base_dir)
            normalized[norm_key] = resolved
            continue

        if norm_key == "resolution":
            normalized[norm_key] = _parse_resolution_value(value)
            continue

        if norm_key in {"scan_all", "preserve_videos"}:
            if not isinstance(value, bool):
                raise ValueError(f"Config key {key} must be a boolean")
            normalized[norm_key] = value
            continue

        if norm_key == "fps":
            normalized[norm_key] = _parse_int_value(key, value)
            continue

        if norm_key in {
            "duration",
            "photo_seconds",
            "video_max_seconds",
            "photo_max_seconds",
            "transition",
            "fade_max_ratio",
            "bg_blur",
            "bgm_volume",
        }:
            normalized[norm_key] = _parse_float_value(key, value)
            continue

        if norm_key in {"preset", "name"}:
            if value is None:
                normalized[norm_key] = None
                continue
            if not isinstance(value, str):
                raise ValueError(f"Config key {key} must be a string")
            normalized[norm_key] = value
            continue

    return normalized


def build_effective_config(
    base: Dict[str, Any],
    preset_name: str | None,
    config_values: Dict[str, Any],
    cli_values: Dict[str, Any],
    cli_provided: Iterable[str],
) -> Dict[str, Any]:
    effective = merge_preset(preset_name, base, provided=set())

    for key, value in config_values.items():
        if key == "preset":
            continue
        if value is not None:
            effective[key] = value

    for key in cli_provided:
        if key in cli_values:
            effective[key] = cli_values[key]

    return effective


def format_effective_config(effective: Dict[str, Any]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for key in CONFIG_PRINT_ORDER:
        if key not in effective:
            continue
        value = effective[key]
        if isinstance(value, Path):
            output[key] = str(value)
        elif isinstance(value, tuple) and len(value) == 2:
            output[key] = f"{value[0]}x{value[1]}"
        else:
            output[key] = value
    return output


def _resolve_path(path: Path, base_dir: Path) -> Path:
    if path.is_absolute():
        return path
    return (base_dir / path).resolve(strict=False)


def _parse_resolution_value(value: Any) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, str):
        m = _RESOLUTION_RE.match(value.strip())
        if not m:
            raise ValueError("resolution must be in WIDTHxHEIGHT format, e.g. 1920x1080")
        return int(m.group(1)), int(m.group(2))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])
    if isinstance(value, dict) and "width" in value and "height" in value:
        return int(value["width"]), int(value["height"])
    raise ValueError("resolution must be WIDTHxHEIGHT string or [width, height]")


def _parse_float_value(name: str, value: Any) -> float:
    try:
        return float(value)
    except Exception as exc:
        raise ValueError(f"Config key {name} must be a number") from exc


def _parse_int_value(name: str, value: Any) -> int:
    try:
        return int(value)
    except Exception as exc:
        raise ValueError(f"Config key {name} must be an integer") from exc
