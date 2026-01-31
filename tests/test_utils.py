"""Tests for `video_engine.utils` utilities."""

from __future__ import annotations

import pytest
from datetime import date

from video_engine.utils import iso_week_to_range


def test_typical_week() -> None:
    start, end = iso_week_to_range("2026-W04")
    assert start == date.fromisocalendar(2026, 4, 1)
    assert end == date.fromisocalendar(2026, 4, 7)


def test_week01_year_boundary() -> None:
    # Week 01 may start in the previous calendar year; ensure correct monday..sunday
    start, end = iso_week_to_range("2021-W01")
    assert start == date.fromisocalendar(2021, 1, 1)
    assert end == date.fromisocalendar(2021, 1, 7)


@pytest.mark.parametrize(
    "invalid",
    ["2026W04", "2026-W4", "abcd-W04", "2026-W00", "2026-W54"],
)
def test_invalid_formats_raise(invalid: str) -> None:
    with pytest.raises(ValueError):
        iso_week_to_range(invalid)
