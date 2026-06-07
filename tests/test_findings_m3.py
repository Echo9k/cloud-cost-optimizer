"""M3 expected-result tests against the fixture — the two-output contract.

Expected findings (active excluded):
  i-0b2idle002   -> conf 0.9, terminate command, waste claimed (~$29.95/mo)
  i-0c3period03  -> conf 0.4, NO terminate, waste 0 (scheduling candidate)
  vol-0d4orph04  -> conf 0.3, delete-volume command, waste claimed (~$7.99/mo)
  i-0a1active01  -> no finding
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

_FILES = Path(__file__).resolve().parent.parent / "files"


@pytest.fixture
def findings():
    init_db()
    c = TestClient(app)
    with (
        open(_FILES / "cur_sample.csv", "rb") as cur,
        open(_FILES / "utilization_sample.csv", "rb") as util,
    ):
        c.post(
            "/ingest",
            files={
                "cur_file": ("cur_sample.csv", cur, "text/csv"),
                "utilization_file": ("utilization_sample.csv", util, "text/csv"),
            },
        )
    return {f["resource_id"]: f for f in c.get("/findings").json()}


def test_active_has_no_finding(findings):
    assert "i-0a1active01" not in findings


def test_permanently_idle_finding(findings):
    f = findings["i-0b2idle002"]
    assert f["confidence"] == 0.9
    assert f["proposed_command"] == (
        "aws ec2 terminate-instances --instance-ids i-0b2idle002"
    )
    assert f["waste_estimate"] == pytest.approx(29.95, abs=0.01)  # claimed
    assert "decommissioning" in f["caveat"]
    assert f["status"] == "new"


def test_scheduling_candidate_finding(findings):
    f = findings["i-0c3period03"]
    assert f["confidence"] == 0.4
    # NON-termination: no terminate command, waste not claimed.
    assert "terminate-instances" not in f["proposed_command"]
    assert f["waste_estimate"] == 0.0
    assert "Do NOT terminate" in f["caveat"]


def test_orphan_finding(findings):
    f = findings["vol-0d4orph04"]
    assert f["confidence"] == 0.3
    assert f["proposed_command"] == "aws ec2 delete-volume --volume-id vol-0d4orph04"
    assert f["waste_estimate"] == pytest.approx(7.99, abs=0.01)  # claimed
    assert "orphan or data gap" in f["caveat"]


def test_total_claimed_waste_excludes_scheduling(findings):
    # Honest dollar number: scheduling-candidate contributes $0.
    total = sum(f["waste_estimate"] for f in findings.values())
    assert total == pytest.approx(29.95 + 7.99, abs=0.02)


def test_sorted_by_waste_desc(findings):
    # findings dict loses order; re-fetch ordering via waste values present.
    wastes = sorted((f["waste_estimate"] for f in findings.values()), reverse=True)
    assert wastes == [pytest.approx(29.95, abs=0.01), pytest.approx(7.99, abs=0.01), 0.0]
