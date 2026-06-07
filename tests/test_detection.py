"""M2 fixture-driven tests: baseline permanent-idle detection.

The fixture IS the spec. At the idle threshold (~15% mean CPU):
- idle i-0b2idle002 (mean 1.75%)   -> flagged, basis="permanently-idle"
- active i-0a1active01 (mean 68.9%) -> not flagged
- periodic i-0c3period03 (mean 45.6%) -> NOT flagged (intended, see below)
- orphan vol-0d4orph04 (no metrics) -> flagged via absence, basis="orphan-no-metrics"

IMPORTANT — periodic-not-flagged is BY DESIGN, not a miss. The periodic instance
is busy every weekday (~62%) and quiet on weekends (3.5%), giving a HIGH overall
mean (45.6%). It is in use, not permanently idle, so M2's idle threshold must not
catch it. M3 adds a SEPARATE weekday/weekend shape detector that surfaces it as a
non-termination *scheduling* candidate. M2 must not widen its threshold to catch it.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import IDLE_MEAN_CPU_THRESHOLD
from app.db import init_db
from app.main import app

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
    return c


def _by_id(client):
    return {s["resource_id"]: s for s in client.get("/detections").json()}


def test_threshold_is_a_defensible_idle_cutoff():
    # Guard against regressing to an underutilization line (e.g. 50%).
    assert IDLE_MEAN_CPU_THRESHOLD <= 20.0


def test_idle_instance_flagged_as_permanently_idle(client):
    sig = _by_id(client)["i-0b2idle002"]
    assert sig["is_idle_candidate"] is True
    assert sig["basis"] == "permanently-idle"
    assert sig["overall_mean_cpu"] < IDLE_MEAN_CPU_THRESHOLD


def test_active_instance_not_flagged(client):
    sig = _by_id(client)["i-0a1active01"]
    assert sig["is_idle_candidate"] is False
    assert sig["basis"] == "active"


def test_periodic_instance_not_flagged_by_design(client):
    # INTENDED: periodic is in use (high overall mean from weekday load), not
    # permanently idle. M3 introduces its own scheduling-candidate path; M2 must
    # not flag it here.
    sig = _by_id(client)["i-0c3period03"]
    assert sig["is_idle_candidate"] is False
    assert sig["basis"] == "active"
    assert sig["overall_mean_cpu"] >= IDLE_MEAN_CPU_THRESHOLD


def test_orphan_flagged_via_absence(client):
    sig = _by_id(client)["vol-0d4orph04"]
    assert sig["is_idle_candidate"] is True
    assert sig["basis"] == "orphan-no-metrics"
    assert sig["overall_mean_cpu"] is None


def test_findings_frozen_at_m0_payload(client):
    # GET /findings must remain the M0 hardcoded payload, untouched by M2.
    data = client.get("/findings").json()
    assert len(data) == 1
    assert data[0]["resource_id"] == "i-0b2idle002"
    assert data[0]["proposed_command"] == (
        "aws ec2 terminate-instances --instance-ids i-0b2idle002"
    )
