"""M2 detection — baseline PERMANENT-IDLE rule.

Operates on the JOINED utilization series only (never cost). Emits a binary
`DetectionSignal`, deliberately NOT a `Finding`: no confidence, caveat,
waste_estimate, or command — those arrive in later milestones.

Three dispositions:
- orphan (empty utilization series) -> flagged via ABSENCE, its own branch,
  never run through the mean. basis="orphan-no-metrics", overall_mean_cpu=None.
- permanently idle (overall-mean CPU < threshold) -> flagged for termination.
- active (mean at/above threshold) -> not flagged.

NOTE: periodic / scheduled-use resources (busy weekdays, quiet weekends) have a
HIGH overall mean (~45% in the fixture). M2's permanent-idle rule correctly does
NOT flag them. M3 adds a SECOND, SEPARATE detector (daily idle-ratio) that
surfaces them as NON-termination scheduling candidates — the threshold is never
widened to catch them.

Disposition precedence:
  orphan (empty series) -> permanently-idle (overall mean < threshold)
  -> scheduling-candidate (idle_ratio in band) -> active (no finding).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import (
    IDLE_MEAN_CPU_THRESHOLD,
    SCHEDULING_IDLE_RATIO_MAX,
    SCHEDULING_IDLE_RATIO_MIN,
)
from app.resources import ResourceView, get_resources

DetectionBasis = Literal[
    "permanently-idle", "scheduling-candidate", "orphan-no-metrics", "active"
]


class DetectionSignal(BaseModel):
    """Binary detection output. NOT a Finding (no confidence/caveat/waste/command)."""

    resource_id: str
    resource_type: str
    is_idle_candidate: bool  # True only for termination dispositions (idle, orphan)
    basis: DetectionBasis
    overall_mean_cpu: float | None  # None for the orphan (no metric series)
    idle_ratio: float | None = None  # daily idle-day fraction; None for the orphan


def _mean_cpu(resource: ResourceView) -> float:
    cpu = _cpu_samples(resource)
    return sum(cpu) / len(cpu)


def _idle_ratio(resource: ResourceView) -> float:
    """Fraction of DAYS whose mean CPU is below the idle threshold.

    Grouped by calendar date (not row index), so fixture re-ordering can't shift
    the result. Reuses IDLE_MEAN_CPU_THRESHOLD at daily grain — no new threshold.
    """
    by_day: dict[object, list[float]] = {}
    for p in resource.utilization:
        if p.metric_name == "CPUUtilization":
            by_day.setdefault(p.timestamp.date(), []).append(p.value)

    daily_means = [sum(vals) / len(vals) for vals in by_day.values()]
    idle_days = sum(1 for m in daily_means if m < IDLE_MEAN_CPU_THRESHOLD)
    return idle_days / len(daily_means)


def _cpu_samples(resource: ResourceView) -> list[float]:
    return [p.value for p in resource.utilization if p.metric_name == "CPUUtilization"]


def detect_resource(resource: ResourceView) -> DetectionSignal:
    """Classify one joined resource view (M2 idle rule + M3 scheduling rule)."""
    # C3: orphan branch first. "No CPU signal" covers BOTH an empty series and a
    # series that carries only non-CPU metrics (e.g. NetworkIn) — either way we
    # have no utilization signal to judge idle, the most deferential case. (This
    # also guards _mean_cpu / _idle_ratio against division by zero.)
    if not _cpu_samples(resource):
        return DetectionSignal(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            is_idle_candidate=True,
            basis="orphan-no-metrics",
            overall_mean_cpu=None,
            idle_ratio=None,
        )

    mean_cpu = _mean_cpu(resource)
    idle_ratio = _idle_ratio(resource)

    # M2: permanently idle -> termination candidate.
    if mean_cpu < IDLE_MEAN_CPU_THRESHOLD:
        return DetectionSignal(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            is_idle_candidate=True,
            basis="permanently-idle",
            overall_mean_cpu=mean_cpu,
            idle_ratio=idle_ratio,
        )

    # M3: scheduled-use shape -> NON-termination scheduling candidate.
    if SCHEDULING_IDLE_RATIO_MIN <= idle_ratio <= SCHEDULING_IDLE_RATIO_MAX:
        return DetectionSignal(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            is_idle_candidate=False,  # in use on a schedule — NOT a kill candidate
            basis="scheduling-candidate",
            overall_mean_cpu=mean_cpu,
            idle_ratio=idle_ratio,
        )

    return DetectionSignal(
        resource_id=resource.resource_id,
        resource_type=resource.resource_type,
        is_idle_candidate=False,
        basis="active",
        overall_mean_cpu=mean_cpu,
        idle_ratio=idle_ratio,
    )


def detect(session: Session) -> list[DetectionSignal]:
    """Run the M2 rule across all joined resources."""
    return [detect_resource(r) for r in get_resources(session)]
