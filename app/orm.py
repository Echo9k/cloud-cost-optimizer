"""ORM persistence models (SQLAlchemy) — TWO separate tables for TWO feeds.

These are storage rows, intentionally distinct from the Pydantic API-contract
models in `app/models.py`. Constraint (M1): two feeds persist as two relations;
utilization is NEVER collapsed into a column on the billing row. The join is
performed at read time (LEFT join, billing-primary), not by merging tables.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BillingLineItemRow(Base):
    """One persisted cost-export row. `resource_id` is the (normalized) join key."""

    __tablename__ = "billing_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    line_item_id: Mapped[str] = mapped_column(String)
    billing_period_start: Mapped[str] = mapped_column(String)
    usage_account_id: Mapped[str] = mapped_column(String)
    line_item_type: Mapped[str] = mapped_column(String)
    usage_start_date: Mapped[str] = mapped_column(String)
    usage_end_date: Mapped[str] = mapped_column(String)
    product_code: Mapped[str] = mapped_column(String)
    usage_type: Mapped[str] = mapped_column(String)
    operation: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str] = mapped_column(String, index=True)  # join key
    usage_amount: Mapped[float] = mapped_column(Float)
    unblended_rate: Mapped[float] = mapped_column(Float)
    unblended_cost: Mapped[float] = mapped_column(Float)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    name_tag: Mapped[str | None] = mapped_column(String, nullable=True)


class UtilizationSampleRow(Base):
    """One persisted utilization sample. `resource_id` is the (normalized) join key."""

    __tablename__ = "utilization_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_id: Mapped[str] = mapped_column(String, index=True)  # join key
    timestamp: Mapped[datetime] = mapped_column()
    namespace: Mapped[str] = mapped_column(String)
    metric_name: Mapped[str] = mapped_column(String)
    statistic: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String)
    period_seconds: Mapped[int] = mapped_column(Integer)


class ApprovalRow(Base):
    """A persisted HUMAN DECISION to approve a finding's proposed command.

    The persistence seam (M4): findings are derived and recomputed on every
    request, but an approval must survive recomputes. We store ONLY the decision,
    never the derived finding. Keyed by resource_id (one approval per resource).

    `approved_basis` is the reconciliation key: an approval is honored only while
    the resource's recomputed disposition still matches it, so an approval of a
    terminate command never rides onto a resource we no longer recommend killing.
    `approved_command` is kept purely as an audit trail of what was approved.
    Approving NEVER executes anything.
    """

    __tablename__ = "approvals"

    resource_id: Mapped[str] = mapped_column(String, primary_key=True)
    approved_basis: Mapped[str] = mapped_column(String)
    approved_command: Mapped[str] = mapped_column(String)
    approved_at: Mapped[datetime] = mapped_column()
