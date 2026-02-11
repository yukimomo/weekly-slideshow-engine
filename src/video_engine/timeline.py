"""Timeline planning utilities.

Build a 60-second timeline by converting MediaItems into ClipPlan entries
and adjusting durations according to rules (trimming or distributing time).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal
import math
import shutil
import subprocess

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
    timeline_mode: str = "even",
    video_weight: float = 2.0,
    video_durations: Dict[Path, float] | None = None,
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

        Timeline modes:
        - even: current behavior (photo_seconds / video_max_seconds + redistribution).
        - weighted: distribute total time by weights (videos get video_weight x photos).
        - preserve-videos: keep video durations (or video_max_seconds fallback) and assign remaining to photos.
    """
    if not items:
        return []

    def _probe_video_duration(path: Path) -> float | None:
        if not path.exists() or not path.is_file():
            return None
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not proc.stdout:
            return None
        try:
            return float(proc.stdout.strip())
        except Exception:
            return None

    def _get_video_duration(path: Path) -> float | None:
        if video_durations and path in video_durations:
            return float(video_durations[path])
        return _probe_video_duration(path)

    def total(pls: List[ClipPlan]) -> float:
        return sum(p.duration for p in pls)

    if timeline_mode not in {"even", "weighted", "preserve-videos"}:
        raise ValueError(f"Unknown timeline_mode: {timeline_mode}")

    if timeline_mode == "preserve-videos":
        plans = []
        photo_indices: List[int] = []
        for it in items:
            if it.kind == "video":
                vdur = _get_video_duration(it.path)
                if vdur is None or vdur <= 0:
                    vdur = float(video_max_seconds)
                plans.append(ClipPlan(path=it.path, kind="video", duration=float(vdur)))
            else:
                photo_indices.append(len(plans))
                plans.append(ClipPlan(path=it.path, kind="photo", duration=0.0))

        total_video = sum(p.duration for p in plans if p.kind == "video")
        remaining = float(target_seconds) - total_video

        if remaining <= 0:
            # Trim only the last video to fit; keep all video plans.
            if plans:
                over = total(plans) - float(target_seconds)
                if over > 0:
                    for p in reversed(plans):
                        if p.kind == "video":
                            p.duration = max(0.0, p.duration - over)
                            break
            return plans

        if photo_indices:
            per_photo = remaining / len(photo_indices)
            for idx in photo_indices:
                plans[idx].duration = per_photo
            leftover = float(target_seconds) - total(plans)
            if abs(leftover) > 1e-6 and plans:
                plans[-1].duration += leftover
        else:
            if plans:
                plans[-1].duration += remaining
        # Normalize total duration to target (final clip absorbs epsilon).
        diff = float(target_seconds) - total(plans)
        if plans and abs(diff) > 1e-6:
            plans[-1].duration += diff
        return plans

    if timeline_mode == "weighted":
        if video_weight <= 0:
            raise ValueError("video_weight must be > 0")
        weights: List[float] = []
        caps: List[float] = []
        for it in items:
            if it.kind == "video":
                weights.append(float(video_weight))
                caps.append(float(video_max_seconds))
            else:
                weights.append(1.0)
                caps.append(float(photo_max_seconds))

        durations = [0.0 for _ in items]
        remaining = float(target_seconds)
        remaining_weight = sum(weights)
        for idx, w in enumerate(weights):
            if remaining_weight <= 0:
                break
            share = remaining * (w / remaining_weight)
            cap = caps[idx]
            durations[idx] = min(share, cap) if cap > 0 else share

        total_assigned = sum(durations)
        if total_assigned > 0:
            scale = float(target_seconds) / total_assigned
            durations = [d * scale for d in durations]

        if durations:
            diff = float(target_seconds) - sum(durations)
            durations[-1] += diff

        plans = [ClipPlan(path=it.path, kind=it.kind, duration=float(dur)) for it, dur in zip(items, durations)]
        return plans

    plans: List[ClipPlan] = []
    video_caps: dict[int, float] = {}
    for idx, it in enumerate(items):
        if it.kind == "photo":
            plans.append(ClipPlan(path=it.path, kind="photo", duration=float(photo_seconds)))
        else:
            vdur = _get_video_duration(it.path)
            if vdur is not None and vdur > 0:
                base = min(float(video_max_seconds), float(vdur))
                video_caps[idx] = float(vdur)
            else:
                base = float(video_max_seconds)
                video_caps[idx] = base
            plans.append(ClipPlan(path=it.path, kind="video", duration=base))

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

    # If under target_seconds, extend videos first (up to actual duration), then distribute photos evenly
    remaining = target_seconds - total(plans)

    # Extend videos up to their caps
    if remaining > 1e-12:
        video_indices = [i for i, p in enumerate(plans) if p.kind == "video"]
        indices = [i for i in video_indices if video_caps.get(i, plans[i].duration) > plans[i].duration]
        while remaining > 1e-12 and indices:
            per = remaining / len(indices)
            progressed = False
            for idx in indices.copy():
                cap = video_caps.get(idx, plans[idx].duration)
                slack = cap - plans[idx].duration
                if slack <= 0:
                    indices.remove(idx)
                    continue
                add = min(per, slack)
                if add > 0:
                    plans[idx].duration += add
                    remaining -= add
                    progressed = True
                if math.isclose(slack, add, abs_tol=1e-12) or add == slack:
                    indices.remove(idx)
            if not progressed:
                break

    # Distribute remaining across photos evenly (set all photo durations equal)
    photo_indices = [i for i, p in enumerate(plans) if p.kind == "photo"]
    if photo_indices and remaining > 1e-12:
        video_total = sum(p.duration for p in plans if p.kind == "video")
        per_photo = max(0.0, (target_seconds - video_total) / len(photo_indices))
        for idx in photo_indices:
            plans[idx].duration = per_photo
        remaining = 0.0

    # If still remaining (e.g., no photos), add to last clip
    if remaining > 1e-12 and plans:
        plans[-1].duration += remaining
        remaining = 0.0

    diff = float(target_seconds) - total(plans)
    if plans and abs(diff) > 1e-6:
        plans[-1].duration += diff
    if abs(float(target_seconds) - total(plans)) > 1e-6:
        raise ValueError("timeline duration drifted from target")
    return plans


def summarize_timeline(plans: List[ClipPlan], target_seconds: float) -> Dict[str, float]:
    photo_plans = [p for p in plans if p.kind == "photo"]
    video_plans = [p for p in plans if p.kind == "video"]
    total_planned = sum(p.duration for p in plans)
    per_photo = sum(p.duration for p in photo_plans) / len(photo_plans) if photo_plans else 0.0
    per_video = sum(p.duration for p in video_plans) / len(video_plans) if video_plans else 0.0
    return {
        "target_seconds": float(target_seconds),
        "total_planned": float(total_planned),
        "photo_count": float(len(photo_plans)),
        "video_count": float(len(video_plans)),
        "per_photo": float(per_photo),
        "per_video": float(per_video),
    }
