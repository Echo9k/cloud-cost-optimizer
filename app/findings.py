"""M3 findings builder — graduates detection signals into real Findings.

Maps each non-active resource's disposition to a `Finding` (the M0 contract
shape, exactly), pulling confidence / caveat / command / waste from config and
the joined cost rows. No placeholder values.

Two-output contract honored:
- waste_estimate ($) is CLAIMED only for high-confidence findings
  (permanently-idle, orphan). The scheduling-candidate claims $0 — we do not
  claim savings on something we are not recommending you delete.
- confidence is a defensible round tier, surfaced with a plain-language caveat.

This module recommends; it never executes. proposed_command is a STRING the
human runs in their own terminal. The scheduling-candidate gets NO terminate
command by design.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import (
    CONFIDENCE_ORPHAN,
    CONFIDENCE_PERMANENTLY_IDLE,
    CONFIDENCE_SCHEDULING_CANDIDATE,
    WASTE_PROJECTION_DAYS,
)
from app.detect import DetectionSignal, detect_resource
from app.models import Finding
from app.resources import ResourceView, get_resources


def _monthly_waste(resource: ResourceView) -> float:
    """Project observed window cost to a 30-day monthly run-rate.

    waste = (sum unblended_cost over window / observed_days) * WASTE_PROJECTION_DAYS.
    observed_days = distinct billing usage-start dates (14 in the fixture).
    """
    total_cost = sum(c.unblended_cost for c in resource.cost_rows)
    observed_days = len({c.usage_start_date for c in resource.cost_rows})
    if observed_days == 0:
        return 0.0
    return round(total_cost / observed_days * WASTE_PROJECTION_DAYS, 2)


def _finding_for(resource: ResourceView, signal: DetectionSignal) -> Finding | None:
    """Build a Finding for one resource, or None if it is active (no finding)."""
    rid = resource.resource_id

    if signal.basis == "permanently-idle":
        return Finding(
            resource_id=rid,
            resource_type=resource.resource_type,
            reason=f"Overall-mean CPU {signal.overall_mean_cpu:.1f}% across the "
            "window — flat and idle every day.",
            confidence=CONFIDENCE_PERMANENTLY_IDLE,
            caveat="Flat low utilization; confirm no out-of-band use before "
            "decommissioning.",
            waste_estimate=_monthly_waste(resource),  # claimed (high confidence)
            proposed_command=f"aws ec2 terminate-instances --instance-ids {rid}",
            status="new",
        )

    if signal.basis == "scheduling-candidate":
        # Recover idle/total day counts for the human-readable caveat text.
        n_idle, n_total = _idle_day_counts(resource)
        return Finding(
            resource_id=rid,
            resource_type=resource.resource_type,
            reason=f"Idle {n_idle} of {n_total} days (overall mean "
            f"{signal.overall_mean_cpu:.1f}%) but active the rest — looks like "
            "scheduled use, not permanent idle.",
            confidence=CONFIDENCE_SCHEDULING_CANDIDATE,
            caveat=f"Idle ~{n_idle} of {n_total} days but active the rest; likely "
            "scheduled use; consider scheduling or scale-to-zero. Do NOT "
            "terminate without confirming the usage pattern.",
            waste_estimate=0.0,  # unquantified — not recommending deletion
            proposed_command="# No automated command. Likely scheduled use — "
            "review the usage pattern; consider an instance scheduler / "
            "scale-to-zero before acting.",
            status="new",
        )

    if signal.basis == "orphan-no-metrics":
        return Finding(
            resource_id=rid,
            resource_type=resource.resource_type,
            reason="Billing rows present but no utilization signal at all — "
            "orphan via join-absence.",
            confidence=CONFIDENCE_ORPHAN,
            caveat="Billing with no utilization signal — orphan or data gap; "
            "confirm before acting.",
            waste_estimate=_monthly_waste(resource),  # claimed (high cost, low conf)
            proposed_command=f"aws ec2 delete-volume --volume-id {rid}",
            status="new",
        )

    # active -> no finding
    return None


def _idle_day_counts(resource: ResourceView) -> tuple[int, int]:
    from app.config import IDLE_MEAN_CPU_THRESHOLD

    by_day: dict[object, list[float]] = {}
    for p in resource.utilization:
        if p.metric_name == "CPUUtilization":
            by_day.setdefault(p.timestamp.date(), []).append(p.value)
    daily_means = [sum(v) / len(v) for v in by_day.values()]
    idle = sum(1 for m in daily_means if m < IDLE_MEAN_CPU_THRESHOLD)
    return idle, len(daily_means)


def build_findings(session: Session) -> list[Finding]:
    """Real findings from joined data, sorted by claimed waste (desc)."""
    findings: list[Finding] = []
    for resource in get_resources(session):
        finding = _finding_for(resource, detect_resource(resource))
        if finding is not None:
            findings.append(finding)
    findings.sort(key=lambda f: f.waste_estimate, reverse=True)
    return findings
