"""M4 tests: approval persists across recomputes; nothing is ever executed.

Verification anchor:
  GET /findings              -> idle instance status "new"
  POST .../approve           -> 200, status "approved" (one row written, nothing run)
  GET /findings (recomputed) -> idle "approved"; orphan + periodic still "new"
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db import Base, SessionLocal, engine, init_db
from app.main import app
from app.orm import ApprovalRow, BillingLineItemRow, UtilizationSampleRow

_FILES = Path(__file__).resolve().parent.parent / "files"
_IDLE = "i-0b2idle002"
_ORPHAN = "vol-0d4orph04"
_PERIODIC = "i-0c3period03"
_ACTIVE = "i-0a1active01"


def _ingest(client):
    with (
        open(_FILES / "cur_sample.csv", "rb") as cur,
        open(_FILES / "utilization_sample.csv", "rb") as util,
    ):
        client.post(
            "/ingest",
            files={
                "cur_file": ("cur_sample.csv", cur, "text/csv"),
                "utilization_file": ("utilization_sample.csv", util, "text/csv"),
            },
        )


@pytest.fixture
def client():
    # Fresh DB each test so approval rows don't leak between cases.
    Base.metadata.drop_all(bind=engine)
    init_db()
    c = TestClient(app)
    _ingest(c)
    return c


def _status(client, resource_id):
    data = {f["resource_id"]: f for f in client.get("/findings").json()}
    return data.get(resource_id, {}).get("status")


def test_approve_roundtrip_survives_recompute(client):
    assert _status(client, _IDLE) == "new"

    resp = client.post(f"/findings/{_IDLE}/approve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "approved"
    assert body["proposed_command"] == (
        f"aws ec2 terminate-instances --instance-ids {_IDLE}"
    )

    # Recomputed from joined data on a fresh request — approval must persist.
    assert _status(client, _IDLE) == "approved"
    # Other findings unaffected.
    assert _status(client, _ORPHAN) == "new"
    assert _status(client, _PERIODIC) == "new"


def test_approve_writes_only_an_approval_row_nothing_executed(client):
    client.post(f"/findings/{_IDLE}/approve")
    with SessionLocal() as s:
        # The only side effect is one approvals row; feed tables are untouched.
        assert s.execute(select(func.count()).select_from(ApprovalRow)).scalar() == 1
        assert s.execute(
            select(func.count()).select_from(BillingLineItemRow)
        ).scalar() == 56
        assert s.execute(
            select(func.count()).select_from(UtilizationSampleRow)
        ).scalar() == 42
        appr = s.get(ApprovalRow, _IDLE)
        assert appr.approved_basis == "permanently-idle"
        assert appr.approved_command.startswith("aws ec2 terminate-instances")


def test_orphan_is_approvable(client):
    resp = client.post(f"/findings/{_ORPHAN}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert _status(client, _ORPHAN) == "approved"


def test_scheduling_candidate_not_approvable(client):
    resp = client.post(f"/findings/{_PERIODIC}/approve")
    assert resp.status_code == 422
    assert "scheduling candidate" in resp.json()["detail"]
    # Still new; no approval persisted.
    assert _status(client, _PERIODIC) == "new"


def test_active_resource_has_no_finding_to_approve(client):
    resp = client.post(f"/findings/{_ACTIVE}/approve")
    assert resp.status_code == 404


def test_unknown_resource_404(client):
    assert client.post("/findings/i-doesnotexist/approve").status_code == 404


def test_idempotent_reapproval(client):
    client.post(f"/findings/{_IDLE}/approve")
    client.post(f"/findings/{_IDLE}/approve")
    with SessionLocal() as s:
        # Upsert by resource_id PK — still exactly one row.
        assert s.execute(select(func.count()).select_from(ApprovalRow)).scalar() == 1


def test_stale_approval_not_honored_after_disposition_change(client):
    # Approve the idle instance, then re-ingest data that turns it ACTIVE.
    client.post(f"/findings/{_IDLE}/approve")
    assert _status(client, _IDLE) == "approved"

    # Re-ingest: same cost feed, but rewrite the idle instance's utilization to a
    # flat-busy series so its disposition is no longer permanently-idle.
    cur = (_FILES / "cur_sample.csv").read_bytes()
    util_lines = (_FILES / "utilization_sample.csv").read_text().splitlines()
    header = util_lines[0]
    rewritten = [header]
    for line in util_lines[1:]:
        if line.startswith(f"{_IDLE},"):
            cols = line.split(",")
            cols[5] = "80.0"  # value column -> busy
            line = ",".join(cols)
        rewritten.append(line)
    client.post(
        "/ingest",
        files={
            "cur_file": ("cur.csv", cur, "text/csv"),
            "utilization_file": ("util.csv", "\n".join(rewritten), "text/csv"),
        },
    )

    # The idle instance is now active -> no finding surfaces. The stale approval
    # row remains dormant and is NOT honored (the safety guard).
    data = {f["resource_id"]: f for f in client.get("/findings").json()}
    assert _IDLE not in data
    with SessionLocal() as s:
        assert s.get(ApprovalRow, _IDLE) is not None  # dormant, not honored
