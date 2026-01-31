"""Timeline planning utilities.

Build a 60-second timeline by converting MediaItems into ClipPlan entries
and adjusting durations according to rules (trimming or distributing time).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal
import math

from .scan import MediaItem


@dataclass
class ClipPlan:
    path: Path
    kind: Literal["photo", "video"]
    duration: float


def build_timeline(
    items: List[MediaItem],
    target_seconds: float = 60.0,
    photo_seconds: float = 2.5,
    video_max_seconds: float = 5.0,
    photo_max_seconds: float = 6.0,
) -> List[ClipPlan]:
    """Build a list of ClipPlan entries whose total duration is target_seconds.

    Rules (MVP):
    - Convert items in order to initial ClipPlans: photos -> photo_seconds, videos -> video_max_seconds
    - If the sum exceeds target_seconds: drop whole clips from the end until sum <= target_seconds,
      then set the last clip's duration to the remaining seconds. If that remainder would be < 0.1s,
      drop the last clip and repeat.
    - If the sum is less than target_seconds: distribute remaining seconds evenly across photo clips,
      capping each at photo_max_seconds. If remaining seconds still remain after capping, add the rest
      to the last clip's duration.
    - Return a deterministic, stable list of ClipPlan objects.
    """
    if not items:
        return []

    plans: List[ClipPlan] = []
    for it in items:
        if it.kind == "photo":
            plans.append(ClipPlan(path=it.path, kind="photo", duration=float(photo_seconds)))
        else:
            plans.append(ClipPlan(path=it.path, kind="video", duration=float(video_max_seconds)))

    def total(pls: List[ClipPlan]) -> float:
        return sum(p.duration for p in pls)

    # Trim if over target_seconds
    if total(plans) > target_seconds:
        # Remove clips from the end while we have more than one clip and still exceed target.
        while len(plans) > 1 and total(plans) > target_seconds:
            plans.pop()

        # If only one clip remains, adjust its duration to the target (if reasonable)
        if len(plans) == 1 and total(plans) > target_seconds:
            remainder = target_seconds
            if remainder >= 0.1:
                plans[0].duration = remainder
                return plans
            else:
                # Can't represent a clip with such a small duration
                return []

        # Otherwise, adjust the last clip to fill the remaining seconds, dropping it if the remainder would be too small
        while plans:
            prev_sum = total(plans[:-1])
            remainder = target_seconds - prev_sum
            if remainder >= 0.1:
                plans[-1].duration = remainder
                break
            else:
                plans.pop()
        return plans

    # If under target_seconds, distribute remaining across photos
    remaining = target_seconds - total(plans)

    # Indices of photo clips
    photo_indices = [i for i, p in enumerate(plans) if p.kind == "photo"]

    if photo_indices:
        # Iteratively distribute remaining seconds evenly, respecting caps
        indices = photo_indices.copy()
        while remaining > 1e-12 and indices:
            per = remaining / len(indices)
            progressed = False
            for idx in indices.copy():
                p = plans[idx]
                cap = photo_max_seconds - p.duration
                if cap <= 0:
                    indices.remove(idx)
                    continue
                add = min(per, cap)
                if add > 0:
                    p.duration += add
                    remaining -= add
                    progressed = True
                if math.isclose(cap, add, abs_tol=1e-12) or add == cap:
                    indices.remove(idx)
            if not progressed:
                break

    # If still remaining (e.g., no photos or capped), add to last clip
    if remaining > 1e-12 and plans:
        plans[-1].duration += remaining
        remaining = 0.0

    return plans
