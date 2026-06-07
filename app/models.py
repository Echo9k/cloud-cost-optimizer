"""API-contract models (Pydantic) for the Cloud Cost Optimizer.

These are the *contract* schemas exchanged over the API. They are intentionally
the single source of truth for shapes named in CLAUDE.md: `BillingLineItem`,
`UtilizationSample`, `Finding`. Treat them as fixed unless the spec changes.

M1 INTENT (noted, not built here): when SQLite/SQLAlchemy arrives, persistence
(ORM row) models live SEPARATELY from these API-contract models. Do not fuse an
API schema with an ORM row — keep the boundary clean. This file stays Pydantic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class BillingLineItem(BaseModel):
    """One row of the cost export (CUR-shaped). Proves a resource *cost money* —
    NOT that it is busy. `usage_amount` is billed quantity (instance-hours,
    GB-Mo), identical at 2% or 90% CPU. Field names map to `cur_sample.csv`.
    """

    line_item_id: str = Field(..., alias="identity/LineItemId")
    billing_period_start: str = Field(..., alias="bill/BillingPeriodStartDate")
    usage_account_id: str = Field(..., alias="lineItem/UsageAccountId")
    line_item_type: str = Field(..., alias="lineItem/LineItemType")
    usage_start_date: str = Field(..., alias="lineItem/UsageStartDate")
    usage_end_date: str = Field(..., alias="lineItem/UsageEndDate")
    product_code: str = Field(..., alias="lineItem/ProductCode")
    usage_type: str = Field(..., alias="lineItem/UsageType")
    operation: str = Field(..., alias="lineItem/Operation")
    # The join key. Normalized before joining (see CLAUDE.md contracts).
    resource_id: str = Field(..., alias="lineItem/ResourceId")
    usage_amount: float = Field(..., alias="lineItem/UsageAmount")
    unblended_rate: float = Field(..., alias="lineItem/UnblendedRate")
    unblended_cost: float = Field(..., alias="lineItem/UnblendedCost")
    product_name: str | None = Field(None, alias="product/ProductName")
    region: str | None = Field(None, alias="product/region")
    name_tag: str | None = Field(None, alias="resourceTags/user/Name")

    model_config = {"populate_by_name": True}


class UtilizationSample(BaseModel):
    """One CloudWatch-shaped metric sample. Utilization is the ONLY signal that
    separates idle from busy — mandatory, not optional. Field names map to
    `utilization_sample.csv`. `resource_id` is the join key into billing.
    """

    resource_id: str
    timestamp: datetime
    namespace: str
    metric_name: str
    statistic: str
    value: float
    unit: str
    period_seconds: int


class Finding(BaseModel):
    """A proposed remediation. Carries TWO distinct axes (never collapsed):
    `waste_estimate` ($, magnitude) and `confidence` (0-1, recommendation
    safety) plus a plain-language `caveat`. `proposed_command` is a STRING the
    human runs in their own terminal — this app never executes it.
    """

    resource_id: str
    resource_type: str
    reason: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    caveat: str
    waste_estimate: float
    proposed_command: str
    status: Literal["new", "approved"] = "new"
