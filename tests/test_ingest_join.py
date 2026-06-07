"""M1 fixture-driven tests: ingest both feeds, verify the billing-primary join.

The fixture IS the spec. Key assertions:
- two tables populated (56 billing rows + 42 utilization rows)
- 4 resources returned (billing-primary: every billed resource appears)
- the i-* instances carry 14 cost rows + 14 utilization samples
- the orphan vol-0d4orph04 carries cost rows and utilization == [] (preserved,
  not dropped, not flagged)
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import SessionLocal, init_db
from app.main import app
from app.orm import BillingLineItemRow, UtilizationSampleRow

_FILES = Path(__file__).resolve().parent.parent / "files"


@pytest.fixture
def client():
    init_db()
    c = TestClient(app)
    with (
        open(_FILES / "cur_sample.csv", "rb") as cur,
        open(_FILES / "utilization_sample.csv", "rb") as util,
    ):
        resp = c.post(
            "/ingest",
            files={
                "cur_file": ("cur_sample.csv", cur, "text/csv"),
                "utilization_file": ("utilization_sample.csv", util, "text/csv"),
            },
        )
    assert resp.status_code == 200
    assert resp.json() == {"billing_rows": 56, "utilization_rows": 42}
    return c


def test_two_tables_populated(client):
    with SessionLocal() as s:
        assert s.execute(select(func.count()).select_from(BillingLineItemRow)).scalar() == 56
        assert s.execute(select(func.count()).select_from(UtilizationSampleRow)).scalar() == 42


def test_resources_returns_every_billed_resource(client):
    data = client.get("/resources").json()
    ids = {r["resource_id"] for r in data}
    assert ids == {"i-0a1active01", "i-0b2idle002", "i-0c3period03", "vol-0d4orph04"}


def test_instances_have_joined_utilization(client):
    data = {r["resource_id"]: r for r in client.get("/resources").json()}
    for rid in ("i-0a1active01", "i-0b2idle002", "i-0c3period03"):
        assert len(data[rid]["cost_rows"]) == 14
        assert len(data[rid]["utilization"]) == 14


def test_orphan_preserved_with_no_metrics(client):
    data = {r["resource_id"]: r for r in client.get("/resources").json()}
    orphan = data["vol-0d4orph04"]
    assert orphan["resource_type"] == "ebs-volume"
    assert len(orphan["cost_rows"]) == 14          # cost survives
    assert orphan["utilization"] == []             # no metric series, NOT dropped


def test_reingest_is_idempotent(client):
    """Clear-and-load: a second POST does not duplicate rows."""
    with (
        open(_FILES / "cur_sample.csv", "rb") as cur,
        open(_FILES / "utilization_sample.csv", "rb") as util,
    ):
        resp = client.post(
            "/ingest",
            files={
                "cur_file": ("cur_sample.csv", cur, "text/csv"),
                "utilization_file": ("utilization_sample.csv", util, "text/csv"),
            },
        )
    assert resp.json() == {"billing_rows": 56, "utilization_rows": 42}
    with SessionLocal() as s:
        assert s.execute(select(func.count()).select_from(BillingLineItemRow)).scalar() == 56
