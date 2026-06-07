"""Ingest: parse the two CSV feeds, validate, normalize the join key, persist.

Flow per feed: raw CSV rows -> validate through the Pydantic API-contract models
(`BillingLineItem` / `UtilizationSample`, alias-mapped to the slash columns) ->
normalize `resource_id` (join-prep) -> write to the corresponding ORM table.

Ingest is clear-and-load: each call truncates both tables then loads, so the
fixture state is deterministic and re-POSTing is idempotent.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import BillingLineItem, UtilizationSample
from app.orm import BillingLineItemRow, UtilizationSampleRow


def normalize_resource_id(resource_id: str) -> str:
    """Join-prep: canonicalize the join key so both feeds agree.

    Real CUR mixes ARNs and bare IDs; the fixtures already use the normalized
    bare-ID form, so this is currently an identity passthrough (trim only). It
    exists as the explicit seam where ARN -> bare-ID reduction will live (Phase
    2). Keep the join keyed on this function's output on BOTH feeds.
    """
    rid = resource_id.strip()
    # Phase-2 seam: if "arn:" in rid: rid = rid.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return rid


def _parse_csv(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig")  # tolerate BOM
    return list(csv.DictReader(io.StringIO(text)))


def ingest_feeds(session: Session, cur_csv: bytes, utilization_csv: bytes) -> dict[str, int]:
    """Parse + validate + normalize + persist both feeds. Returns row counts."""
    billing_rows = [
        BillingLineItem.model_validate(row) for row in _parse_csv(cur_csv)
    ]
    util_rows = [
        UtilizationSample.model_validate(row) for row in _parse_csv(utilization_csv)
    ]

    # Clear-and-load: deterministic fixture state, idempotent re-POST.
    session.execute(delete(BillingLineItemRow))
    session.execute(delete(UtilizationSampleRow))

    session.add_all(
        BillingLineItemRow(
            line_item_id=b.line_item_id,
            billing_period_start=b.billing_period_start,
            usage_account_id=b.usage_account_id,
            line_item_type=b.line_item_type,
            usage_start_date=b.usage_start_date,
            usage_end_date=b.usage_end_date,
            product_code=b.product_code,
            usage_type=b.usage_type,
            operation=b.operation,
            resource_id=normalize_resource_id(b.resource_id),  # join-prep
            usage_amount=b.usage_amount,
            unblended_rate=b.unblended_rate,
            unblended_cost=b.unblended_cost,
            product_name=b.product_name,
            region=b.region,
            name_tag=b.name_tag,
        )
        for b in billing_rows
    )
    session.add_all(
        UtilizationSampleRow(
            resource_id=normalize_resource_id(u.resource_id),  # join-prep
            timestamp=u.timestamp,
            namespace=u.namespace,
            metric_name=u.metric_name,
            statistic=u.statistic,
            value=u.value,
            unit=u.unit,
            period_seconds=u.period_seconds,
        )
        for u in util_rows
    )
    session.commit()

    return {"billing_rows": len(billing_rows), "utilization_rows": len(util_rows)}
