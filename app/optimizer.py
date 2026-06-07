"""The optimization rules engine.

Each rule is a pure function: given a Resource, it returns a ``RuleHit`` or
``None``. Keeping rules pure makes them trivially unit-testable and lets the
scanner stay a thin orchestration layer. Adding a new rule is a one-line
registration in ``RULES``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Recommendation,
    RecommendationStatus,
    RecommendationType,
    Resource,
    ResourceState,
    Severity,
)

COMPUTE_SERVICES = {"ec2", "vm", "compute", "gce"}


@dataclass(frozen=True)
class RuleHit:
    rec_type: RecommendationType
    severity: Severity
    estimated_monthly_savings: float
    suggested_action: str
    rationale: str


Rule = Callable[[Resource], RuleHit | None]


def _is_compute(resource: Resource) -> bool:
    return resource.service.lower() in COMPUTE_SERVICES


def rule_idle_compute(resource: Resource) -> RuleHit | None:
    """Running compute with negligible CPU is wasted spend — recommend stop."""
    if not _is_compute(resource) or resource.state != ResourceState.RUNNING:
        return None
    if resource.cpu_utilization >= settings.IDLE_CPU_PCT:
        return None
    return RuleHit(
        rec_type=RecommendationType.IDLE,
        severity=Severity.HIGH,
        estimated_monthly_savings=round(resource.monthly_cost, 2),
        suggested_action="stop",
        rationale=(
            f"CPU averaged {resource.cpu_utilization:.1f}% "
            f"(< {settings.IDLE_CPU_PCT:.0f}% idle threshold). "
            f"Stopping reclaims the full ${resource.monthly_cost:.2f}/mo."
        ),
    )


def rule_rightsize_compute(resource: Resource) -> RuleHit | None:
    """Lightly-used compute can drop a size tier for partial savings."""
    if not _is_compute(resource) or resource.state != ResourceState.RUNNING:
        return None
    if not (
        settings.IDLE_CPU_PCT <= resource.cpu_utilization < settings.RIGHTSIZE_CPU_PCT
    ):
        return None
    savings = resource.monthly_cost * settings.RIGHTSIZE_SAVINGS_FRACTION
    return RuleHit(
        rec_type=RecommendationType.RIGHTSIZE,
        severity=Severity.MEDIUM,
        estimated_monthly_savings=round(savings, 2),
        suggested_action="downsize",
        rationale=(
            f"CPU averaged {resource.cpu_utilization:.1f}% — sustained headroom. "
            f"Dropping one size tier saves ~${savings:.2f}/mo."
        ),
    )


def rule_orphaned(resource: Resource) -> RuleHit | None:
    """Unattached storage/IPs accrue cost while serving nothing."""
    if resource.state != ResourceState.UNATTACHED:
        return None
    return RuleHit(
        rec_type=RecommendationType.ORPHANED,
        severity=Severity.HIGH,
        estimated_monthly_savings=round(resource.monthly_cost, 2),
        suggested_action="delete",
        rationale=(
            f"Resource is unattached yet billing ${resource.monthly_cost:.2f}/mo. "
            "Deleting reclaims the full amount."
        ),
    )


def rule_stale(resource: Resource) -> RuleHit | None:
    """Stopped resources older than the stale window are cleanup candidates."""
    if resource.state != ResourceState.STOPPED:
        return None
    if resource.age_days < settings.STALE_AGE_DAYS:
        return None
    return RuleHit(
        rec_type=RecommendationType.STALE,
        severity=Severity.MEDIUM,
        estimated_monthly_savings=round(resource.monthly_cost, 2),
        suggested_action="delete",
        rationale=(
            f"Stopped for {resource.age_days} days "
            f"(> {settings.STALE_AGE_DAYS}-day stale window). "
            "Still incurs storage cost; recommend deletion."
        ),
    )


def rule_untagged(resource: Resource) -> RuleHit | None:
    """Governance rule: flag missing cost-allocation tags (no direct savings)."""
    missing = [t for t in settings.REQUIRED_TAGS if t not in (resource.tags or {})]
    if not missing:
        return None
    return RuleHit(
        rec_type=RecommendationType.UNTAGGED,
        severity=Severity.LOW,
        estimated_monthly_savings=0.0,
        suggested_action="tag",
        rationale=(
            f"Missing required tag(s): {', '.join(missing)}. "
            "Untagged spend cannot be attributed to a cost center."
        ),
    )


# Registration order also defines evaluation order. Idle and rightsize are
# mutually exclusive by construction (disjoint CPU bands).
RULES: list[Rule] = [
    rule_idle_compute,
    rule_rightsize_compute,
    rule_orphaned,
    rule_stale,
    rule_untagged,
]


def evaluate(resource: Resource) -> list[RuleHit]:
    """Run every rule against a resource and collect the hits."""
    hits: list[RuleHit] = []
    for rule in RULES:
        hit = rule(resource)
        if hit is not None:
            hits.append(hit)
    return hits


def scan(db: Session) -> tuple[int, int, float]:
    """Scan all resources, refreshing open recommendations.

    Idempotent: existing OPEN recommendations are cleared before rescanning so
    repeated scans don't create duplicates. APPLIED/DISMISSED history is kept.

    Returns ``(scanned_resources, recommendations_created, potential_savings)``.
    """
    resources = db.query(Resource).all()

    # Clear stale OPEN recommendations; preserve actioned history.
    db.query(Recommendation).filter(
        Recommendation.status == RecommendationStatus.OPEN
    ).delete(synchronize_session=False)

    created = 0
    potential = 0.0
    for resource in resources:
        if resource.state == ResourceState.TERMINATED:
            continue
        for hit in evaluate(resource):
            db.add(
                Recommendation(
                    resource_id=resource.id,
                    rec_type=hit.rec_type,
                    severity=hit.severity,
                    status=RecommendationStatus.OPEN,
                    estimated_monthly_savings=hit.estimated_monthly_savings,
                    suggested_action=hit.suggested_action,
                    rationale=hit.rationale,
                )
            )
            created += 1
            potential += hit.estimated_monthly_savings

    db.commit()
    return len(resources), created, round(potential, 2)
