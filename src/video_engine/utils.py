"""Utility helpers for video_engine."""

from __future__ import annotations

import re
from datetime import date
from typing import Tuple

_ISO_WEEK_RE = re.compile(r"^(\d{4})-W(0[1-9]|[1-4][0-9]|5[0-3])$")


def iso_week_to_range(iso_week: str) -> Tuple[date, date]:
    """Convert an ISO week string to a (start_date, end_date) tuple.

    The input must be strictly formatted as ``YYYY-Www`` where ``ww`` is
    two digits from 01 to 53. The returned dates are the Monday (start)
    and Sunday (end) of that ISO week.

    Raises
    -----
    ValueError
        If the format is invalid or the year/week combination is not
        valid (e.g., week 53 in a year without 53 ISO weeks).
    """
    if not isinstance(iso_week, str):
        raise ValueError(f"iso_week must be a string, got {type(iso_week)!r}")

    m = _ISO_WEEK_RE.match(iso_week)
    if not m:
        raise ValueError(
            f"Invalid ISO week format: {iso_week!r}. Expected 'YYYY-Www' with ww between 01 and 53."
        )

    year = int(m.group(1))
    week = int(m.group(2))

    try:
        start = date.fromisocalendar(year, week, 1)  # Monday
        end = date.fromisocalendar(year, week, 7)  # Sunday
    except ValueError as exc:  # Propagate with clearer message
        raise ValueError(f"Invalid ISO week {iso_week!r}: {exc}") from exc

    return start, end
