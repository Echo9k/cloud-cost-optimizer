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
HIGH overall mean (~45% in the fixture) and are intentionally NOT flagged here.
They are in use, not idle. M3 adds a SEPARATE weekday/weekend shape detector
that surfaces them as non-termination scheduling candidates — M2 must not widen
its threshold to catch them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import IDLE_MEAN_CPU_THRESHOLD
from app.resources import ResourceView, get_resources

DetectionBasis = Literal["permanently-idle", "orphan-no-metrics", "active"]


class DetectionSignal(BaseModel):
    """Binary detection output. NOT a Finding (no confidence/caveat/waste/command)."""

    resource_id: str
    resource_type: str
    is_idle_candidate: bool
    basis: DetectionBasis
    overall_mean_cpu: float | None  # None for the orphan (no metric series)


def _mean_cpu(resource: ResourceView) -> float:
    cpu = [p.value for p in resource.utilization if p.metric_name == "CPUUtilization"]
    return sum(cpu) / len(cpu)


def detect_resource(resource: ResourceView) -> DetectionSignal:
    """Apply the M2 permanent-idle rule to one joined resource view."""
    # C3: orphan branch first — empty series, flagged via absence, never averaged.
    if not resource.utilization:
        return DetectionSignal(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            is_idle_candidate=True,
            basis="orphan-no-metrics",
            overall_mean_cpu=None,
        )

    mean_cpu = _mean_cpu(resource)
    if mean_cpu < IDLE_MEAN_CPU_THRESHOLD:
        return DetectionSignal(
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            is_idle_candidate=True,
            basis="permanently-idle",
            overall_mean_cpu=mean_cpu,
        )

    return DetectionSignal(
        resource_id=resource.resource_id,
        resource_type=resource.resource_type,
        is_idle_candidate=False,
        basis="active",
        overall_mean_cpu=mean_cpu,
    )


def detect(session: Session) -> list[DetectionSignal]:
    """Run the M2 rule across all joined resources."""
    return [detect_resource(r) for r in get_resources(session)]
