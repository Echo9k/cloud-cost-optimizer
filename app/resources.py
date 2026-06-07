"""Read-side: the LEFT join that powers GET /resources.

Billing is the PRIMARY side: every billed resource appears. Utilization attaches
where it exists and is an empty list where it does not (the orphan case is
preserved, not dropped). This returns RAW joined data — no detection, no
threshold, no classification. That is M2+.

The response models below are read-side view schemas, kept distinct from the
three API-contract models in `app/models.py`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.orm import BillingLineItemRow, UtilizationSampleRow


class CostRow(BaseModel):
    line_item_id: str
    usage_start_date: str
    usage_end_date: str
    product_code: str
    usage_type: str
    operation: str
    usage_amount: float
    unblended_rate: float
    unblended_cost: float
    region: str | None = None
    name_tag: str | None = None


class UtilizationPoint(BaseModel):
    timestamp: datetime
    metric_name: str
    statistic: str
    value: float
    unit: str
    period_seconds: int


class ResourceView(BaseModel):
    """One resource with its cost rows and (left-joined) utilization series."""

    resource_id: str
    resource_type: str
    cost_rows: list[CostRow]
    utilization: list[UtilizationPoint]  # [] when no metric rows exist (orphan)


def _derive_resource_type(usage_type: str, resource_id: str) -> str:
    """Coarse grouping label only — NOT a classification/detection signal.

    Derived from the resource-id prefix (and usage_type as a fallback hint).
    """
    if resource_id.startswith("vol-") or "VolumeUsage" in usage_type:
        return "ebs-volume"
    if resource_id.startswith("i-") or "BoxUsage" in usage_type:
        return "ec2-instance"
    return "unknown"


def get_resources(session: Session) -> list[ResourceView]:
    """Billing-primary LEFT join on resource_id. Every billed resource appears."""
    billing = session.execute(select(BillingLineItemRow)).scalars().all()
    util = session.execute(select(UtilizationSampleRow)).scalars().all()

    # Group utilization by resource_id (the right side of the LEFT join).
    util_by_resource: dict[str, list[UtilizationSampleRow]] = {}
    for u in util:
        util_by_resource.setdefault(u.resource_id, []).append(u)

    # Group billing by resource_id (the primary side).
    billing_by_resource: dict[str, list[BillingLineItemRow]] = {}
    for b in billing:
        billing_by_resource.setdefault(b.resource_id, []).append(b)

    views: list[ResourceView] = []
    for resource_id, cost_rows in billing_by_resource.items():
        first = cost_rows[0]
        samples = util_by_resource.get(resource_id, [])  # [] = orphan, preserved
        views.append(
            ResourceView(
                resource_id=resource_id,
                resource_type=_derive_resource_type(first.usage_type, resource_id),
                cost_rows=[
                    CostRow(
                        line_item_id=c.line_item_id,
                        usage_start_date=c.usage_start_date,
                        usage_end_date=c.usage_end_date,
                        product_code=c.product_code,
                        usage_type=c.usage_type,
                        operation=c.operation,
                        usage_amount=c.usage_amount,
                        unblended_rate=c.unblended_rate,
                        unblended_cost=c.unblended_cost,
                        region=c.region,
                        name_tag=c.name_tag,
                    )
                    for c in cost_rows
                ],
                utilization=[
                    UtilizationPoint(
                        timestamp=s.timestamp,
                        metric_name=s.metric_name,
                        statistic=s.statistic,
                        value=s.value,
                        unit=s.unit,
                        period_seconds=s.period_seconds,
                    )
                    for s in samples
                ],
            )
        )

    views.sort(key=lambda v: v.resource_id)
    return views
