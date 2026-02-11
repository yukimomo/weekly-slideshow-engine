from video_engine.presets import build_base_config, detect_provided_options, merge_preset


def test_no_preset_keeps_base():
    base = {
        "resolution": (1280, 720),
        "duration": 8.0,
        "transition": 0.3,
        "bg_blur": 6.0,
    }
    eff = merge_preset(None, base, set())
    assert eff == base


def test_preset_applies_defaults():
    base = {
        "resolution": None,
        "duration": 8.0,
        "transition": 0.1,
        "bg_blur": 0.0,
    }
    eff = merge_preset("youtube", base, set())
    assert eff["resolution"] == (1920, 1080)
    assert eff["duration"] == 60.0
    assert eff["transition"] == 0.3
    assert eff["bg_blur"] == 6.0


def test_cli_override_beats_preset():
    base = {
        "resolution": (1920, 1080),  # user provided via CLI
        "duration": 30.0,            # user provided via CLI
        "transition": 0.25,          # user provided via CLI
        "bg_blur": 12.0,             # user provided via CLI
    }
    # Mark all options as explicitly provided
    provided = {"resolution", "duration", "transition", "bg_blur"}
    eff = merge_preset("mobile", base, provided)
    # Preset should NOT override user provided values
    assert eff["resolution"] == (1920, 1080)
    assert eff["duration"] == 30.0
    assert eff["transition"] == 0.25
    assert eff["bg_blur"] == 12.0


def test_partial_override():
    base = {
        "resolution": None,         # not provided
        "duration": 60.0,           # user provided
        "transition": 0.3,          # user provided
        "bg_blur": 6.0,             # user provided
    }
    provided = {"duration", "transition", "bg_blur"}
    eff = merge_preset("mobile", base, provided)
    assert eff["resolution"] == (1080, 1920)
    assert eff["duration"] == 60.0
    assert eff["transition"] == 0.3
    assert eff["bg_blur"] == 6.0


def test_bgm_volume_defaults_and_overrides():
    base = build_base_config()
    eff = merge_preset("youtube", base, set())
    assert eff["bgm_volume"] == 10.0

    base = build_base_config()
    base["bgm_volume"] = 25.0
    eff = merge_preset("mobile", base, {"bgm_volume"})
    assert eff["bgm_volume"] == 25.0


def test_detect_provided_options_includes_bgm_volume():
    argv = ["--bgm-volume", "15", "--duration", "60"]
    provided = detect_provided_options(argv)
    assert "bgm_volume" in provided
    assert "duration" in provided


def test_build_base_config_defaults():
    base = build_base_config()
    assert base["duration"] == 8.0
    assert base["transition"] == 0.3
    assert base["bg_blur"] == 6.0
    assert base["bgm_volume"] == 10.0
    assert base["resolution"] is None
