"""Tests for timeline building logic."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import math

import pytest

from video_engine.timeline import build_timeline, ClipPlan
from video_engine.scan import MediaItem


def _mk_item(i: int, kind: str = "photo") -> MediaItem:
    return MediaItem(path=Path(f"p{i}.{ 'jpg' if kind=='photo' else 'mp4' }"), kind=kind, timestamp=datetime(2026,1,1,0,0, i))


def total_duration(plans: list[ClipPlan]) -> float:
    return sum(p.duration for p in plans)


def test_empty_returns_empty():
    assert build_timeline([]) == []


def test_ten_photos_fill_to_target_and_not_exceed_max():
    items = [_mk_item(i, "photo") for i in range(10)]
    plans = build_timeline(items, target_seconds=60.0, photo_seconds=2.5, photo_max_seconds=6.0)

    assert len(plans) == 10
    # Each should be equal when distributing remaining time
    assert all(math.isclose(p.duration, plans[0].duration, rel_tol=0, abs_tol=1e-12) for p in plans)
    assert math.isclose(total_duration(plans), 60.0, rel_tol=0, abs_tol=1e-6)


def test_trimming_excess_from_end():
    # 13 videos -> each 5s -> 65 total -> should keep 12 with total 60
    items = [_mk_item(i, "video") for i in range(13)]
    plans = build_timeline(items, target_seconds=60.0, video_max_seconds=5.0)

    assert len(plans) == 12
    assert math.isclose(total_duration(plans), 60.0, rel_tol=0, abs_tol=1e-6)
    # all durations should be positive
    assert all(p.duration > 0 for p in plans)


def test_mixed_photos_and_videos_photos_extended_first():
    items = [_mk_item(i, "photo") for i in range(5)] + [_mk_item(i+5, "video") for i in range(5)]
    plans = build_timeline(items, target_seconds=60.0, photo_seconds=2.5, video_max_seconds=5.0, photo_max_seconds=6.0)

    assert math.isclose(total_duration(plans), 60.0, rel_tol=0, abs_tol=1e-6)
    # Photo durations are equal after distribution
    photo_plans = [p for p in plans if p.kind == "photo"]
    assert all(math.isclose(p.duration, photo_plans[0].duration, rel_tol=0, abs_tol=1e-12) for p in photo_plans)


def test_only_videos_under_target_last_extended():
    items = [_mk_item(i, "video") for i in range(5)]
    plans = build_timeline(items, target_seconds=60.0, video_max_seconds=5.0)

    assert math.isclose(total_duration(plans), 60.0, rel_tol=0, abs_tol=1e-6)
    # Last clip should be larger than initial video_max_seconds
    assert plans[-1].duration > 5.0


def test_weighted_mode_allocates_by_ratio():
    items = [_mk_item(i, "photo") for i in range(10)] + [_mk_item(i + 10, "video") for i in range(2)]
    plans = build_timeline(
        items,
        target_seconds=60.0,
        timeline_mode="weighted",
        video_weight=3.0,
        photo_max_seconds=100.0,
        video_max_seconds=100.0,
    )
    photo_plans = [p for p in plans if p.kind == "photo"]
    video_plans = [p for p in plans if p.kind == "video"]
    assert math.isclose(total_duration(plans), 60.0, rel_tol=0, abs_tol=1e-6)
    assert math.isclose(video_plans[0].duration, photo_plans[0].duration * 3.0, rel_tol=0, abs_tol=1e-6)


def test_preserve_videos_mode_uses_video_durations():
    items = [_mk_item(i, "video") for i in range(2)] + [_mk_item(i + 2, "photo") for i in range(2)]
    durations = {items[0].path: 20.0, items[1].path: 20.0}
    plans = build_timeline(
        items,
        target_seconds=60.0,
        timeline_mode="preserve-videos",
        video_durations=durations,
    )
    assert math.isclose(total_duration(plans), 60.0, rel_tol=0, abs_tol=1e-6)
    photo_plans = [p for p in plans if p.kind == "photo"]
    assert all(math.isclose(p.duration, 10.0, rel_tol=0, abs_tol=1e-6) for p in photo_plans)


def test_preserve_videos_trims_when_over_target():
    items = [_mk_item(i, "video") for i in range(2)]
    durations = {items[0].path: 40.0, items[1].path: 40.0}
    plans = build_timeline(
        items,
        target_seconds=60.0,
        timeline_mode="preserve-videos",
        video_durations=durations,
    )
    assert len(plans) == 2
    assert math.isclose(total_duration(plans), 60.0, rel_tol=0, abs_tol=1e-6)
    assert math.isclose(plans[0].duration, 40.0, rel_tol=0, abs_tol=1e-6)
    assert math.isclose(plans[1].duration, 20.0, rel_tol=0, abs_tol=1e-6)
