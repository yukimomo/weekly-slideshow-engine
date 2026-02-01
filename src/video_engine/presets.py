from __future__ import annotations

from typing import Dict, Optional, Tuple, Set

# Preset definitions: values act as defaults which can be overridden by CLI flags.
# Duration choice:
# - youtube: 60s
# - mobile: 60s (keep consistent 1-min output)
# - preview: 8s
PRESETS: Dict[str, Dict[str, object]] = {
    "youtube": {
        "resolution": (1920, 1080),
        "transition": 0.3,
        "bg_blur": 6.0,
        "bgm_volume": 60.0,
        "duration": 60.0,
    },
    "mobile": {
        "resolution": (1080, 1920),
        "transition": 0.25,
        "bg_blur": 8.0,
        "bgm_volume": 60.0,
        "duration": 60.0,
    },
    "preview": {
        "resolution": (1280, 720),
        "transition": 0.2,
        "bg_blur": 4.0,
        "bgm_volume": 60.0,
        "duration": 8.0,
    },
}

OPTION_KEYS = {"resolution", "duration", "transition", "bg_blur", "bgm_volume"}


def merge_preset(
    preset_name: Optional[str],
    base: Dict[str, object],
    provided: Set[str],
) -> Dict[str, object]:
    """Merge preset values into a base config, respecting explicitly provided options.

    Rules:
    - If preset_name is None or not recognized, return base unchanged.
    - Apply preset values only for keys not in `provided`.
    - Keys considered: resolution, duration, transition, bg_blur.
    """
    if not preset_name:
        return base
    preset = PRESETS.get(preset_name)
    if not preset:
        return base

    effective = dict(base)
    for k in OPTION_KEYS:
        if k in preset and k not in provided:
            effective[k] = preset[k]
    return effective


def detect_provided_options(argv_tokens: Optional[list[str]]) -> Set[str]:
    """Detect which CLI options were explicitly provided by scanning argv tokens.

    Returns a set of option keys among OPTION_KEYS.
    Handles forms like:
    - --duration 60
    - --duration=60
    - --resolution 1920x1080
    - --resolution=1920x1080
    """
    provided: Set[str] = set()
    if not argv_tokens:
        return provided

    def mark_if_present(name: str, key: str):
        for t in argv_tokens:
            if t == name or t.startswith(name + "="):
                provided.add(key)
                break

    mark_if_present("--resolution", "resolution")
    mark_if_present("--duration", "duration")
    mark_if_present("--transition", "transition")
    mark_if_present("--bg-blur", "bg_blur")
    return provided
