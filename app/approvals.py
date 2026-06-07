"""M4 approval — persisting a human decision, never executing anything.

Approving a finding writes ONE row to the `approvals` table and returns the
finding with status flipped to "approved". It runs no command, calls no cloud
API, and holds no credential that can mutate anything. The proposed_command
stays a string the human runs in their own terminal — that copy-paste step is
the confirmation layer, by design.

Only ACTIONABLE findings (those carrying a real decommission command) are
approvable: permanently-idle and orphan. The scheduling-candidate is a
NON-termination finding (its command is a review note), so it is NOT approvable —
approving a non-recommendation would imply we sanctioned a deletion we
deliberately refused to recommend.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.findings import build_findings_with_basis
from app.models import Finding
from app.orm import ApprovalRow

# Dispositions that carry a real decommission command and may be approved.
ACTIONABLE_BASES = {"permanently-idle", "orphan-no-metrics"}


class FindingNotFound(Exception):
    """No current finding exists for the given resource_id (active or unknown)."""


class FindingNotApprovable(Exception):
    """The finding exists but is a non-termination (scheduling) candidate."""


def approve(session: Session, resource_id: str) -> Finding:
    """Approve the actionable finding for resource_id. Persists; never executes."""
    match = next(
        (
            (finding, basis)
            for finding, basis in build_findings_with_basis(session)
            if finding.resource_id == resource_id
        ),
        None,
    )
    if match is None:
        raise FindingNotFound(resource_id)

    finding, basis = match
    if basis not in ACTIONABLE_BASES:
        raise FindingNotApprovable(resource_id)

    # Upsert the decision (one approval per resource). NO command is executed.
    approval = session.get(ApprovalRow, resource_id)
    if approval is None:
        approval = ApprovalRow(resource_id=resource_id)
        session.add(approval)
    approval.approved_basis = basis
    approval.approved_command = finding.proposed_command
    approval.approved_at = datetime.now(timezone.utc)
    session.commit()

    finding.status = "approved"
    return finding
