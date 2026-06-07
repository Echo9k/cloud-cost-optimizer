"""The remediation engine.

Translates an approved recommendation into a state change on the (simulated)
cloud resource. Safe by default: ``dry_run=True`` produces a SIMULATED audit
record and changes nothing. Only an explicit ``dry_run=False`` mutates the
resource and books realized savings.

In a production deployment the ``_apply_*`` handlers would call the provider
SDK (boto3, etc.). Here they mutate the local model so the full audit and
savings-tracking workflow is exercisable end-to-end.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    Recommendation,
    RecommendationStatus,
    RemediationAction,
    RemediationStatus,
    Resource,
    ResourceState,
)


class RemediationError(Exception):
    """Raised when a recommendation cannot be remediated."""


# Maps a recommendation's suggested action to the resulting resource state.
_ACTION_TARGET_STATE: dict[str, ResourceState | None] = {
    "stop": ResourceState.STOPPED,
    "delete": ResourceState.TERMINATED,
    "downsize": None,  # resource stays running, cost is reduced in place
    "tag": None,  # governance only, no state change
}


def remediate(
    db: Session, recommendation: Recommendation, dry_run: bool = True
) -> RemediationAction:
    """Execute (or simulate) remediation for a recommendation."""
    if recommendation.status != RecommendationStatus.OPEN:
        raise RemediationError(
            f"Recommendation {recommendation.id} is "
            f"'{recommendation.status.value}', not open."
        )

    action = recommendation.suggested_action
    if action not in _ACTION_TARGET_STATE:
        raise RemediationError(f"Unknown remediation action '{action}'.")

    resource: Resource = recommendation.resource
    savings = recommendation.estimated_monthly_savings

    if dry_run:
        record = RemediationAction(
            recommendation_id=recommendation.id,
            action_type=action,
            dry_run=True,
            status=RemediationStatus.SIMULATED,
            realized_savings=0.0,
            detail=(
                f"DRY RUN: would '{action}' resource {resource.external_id} "
                f"for an estimated ${savings:.2f}/mo. No changes made."
            ),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    # --- Real (simulated cloud) apply ------------------------------------
    target_state = _ACTION_TARGET_STATE[action]
    if target_state is not None:
        resource.state = target_state
    if action == "downsize":
        resource.monthly_cost = round(resource.monthly_cost - savings, 2)

    recommendation.status = RecommendationStatus.APPLIED

    record = RemediationAction(
        recommendation_id=recommendation.id,
        action_type=action,
        dry_run=False,
        status=RemediationStatus.APPLIED,
        realized_savings=savings,
        detail=(
            f"Applied '{action}' to {resource.external_id}; "
            f"realized ${savings:.2f}/mo savings."
        ),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
