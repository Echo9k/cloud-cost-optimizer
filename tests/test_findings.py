"""Contract smoke test for GET /findings.

M3 cutover: /findings now returns REAL findings derived from the joined data
(no more hardcoded payload). This asserts the response still matches the M0
`Finding` contract exactly, and that the endpoint is empty before any ingest.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, init_db
from app.main import app
from app.models import Finding

_FILES = Path(__file__).resolve().parent.parent / "files"


@pytest.fixture
def client():
    # Fresh DB each test so approval rows from other suites don't leak in.
    Base.metadata.drop_all(bind=engine)
    init_db()
    return TestClient(app)


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


def test_findings_match_contract_shape(client):
    _ingest(client)
    resp = client.get("/findings")
    assert resp.status_code == 200

    payload = resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 3  # idle, scheduling-candidate, orphan (active excluded)

    for item in payload:
        finding = Finding.model_validate(item)  # raises if shape drifts
        assert 0.0 <= finding.confidence <= 1.0
        assert finding.caveat
        assert isinstance(finding.proposed_command, str) and finding.proposed_command
        assert finding.status == "new"


def test_findings_empty_before_ingest(client):
    # client fixture already starts from a fresh DB; no ingest here.
    resp = client.get("/findings")
    assert resp.status_code == 200
    assert resp.json() == []


def test_dashboard_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
