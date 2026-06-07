"""M6 edge-case fixtures — boundary behavior + the surfaced no-CPU-signal bug.

See files/EDGE_CASES.md for the spec. No thresholds/logic were changed to make
these pass; case C is the genuine bug fix (utilization rows with no CPU metric
previously crashed detection with ZeroDivisionError).
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine, init_db
from app.main import app

_FILES = Path(__file__).resolve().parent.parent / "files"


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    init_db()
    c = TestClient(app)
    with (
        open(_FILES / "edge_cur_sample.csv", "rb") as cur,
        open(_FILES / "edge_utilization_sample.csv", "rb") as util,
    ):
        resp = c.post(
            "/ingest",
            files={
                "cur_file": ("edge_cur_sample.csv", cur, "text/csv"),
                "utilization_file": ("edge_utilization_sample.csv", util, "text/csv"),
            },
        )
    assert resp.status_code == 200
    return c


def _detections(client):
    return {d["resource_id"]: d for d in client.get("/detections").json()}


def _findings(client):
    return {f["resource_id"]: f for f in client.get("/findings").json()}


def test_case_a_exact_threshold_is_active(client):
    # mean == 15.0 is NOT < 15.0 -> active, no finding (exclusive boundary).
    det = _detections(client)["i-0edgebound15"]
    assert det["basis"] == "active"
    assert det["is_idle_candidate"] is False
    assert "i-0edgebound15" not in _findings(client)


def test_case_b_scheduling_band_max_is_inclusive(client):
    det = _detections(client)["i-0edgesched60"]
    assert det["basis"] == "scheduling-candidate"
    assert det["idle_ratio"] == pytest.approx(0.60)
    f = _findings(client)["i-0edgesched60"]
    assert f["confidence"] == 0.4
    assert f["waste_estimate"] == 0.0
    assert "terminate-instances" not in f["proposed_command"]


def test_case_c_no_cpu_metric_is_orphan_not_crash(client):
    # Regression: utilization rows with only NetworkIn used to crash detection.
    det = _detections(client)["i-0edgenocpu0"]
    assert det["basis"] == "orphan-no-metrics"
    assert det["overall_mean_cpu"] is None
    f = _findings(client)["i-0edgenocpu0"]
    assert f["confidence"] == 0.3


def test_case_d_reverse_orphan_not_surfaced(client):
    # Utilization without a billing row -> billing-primary join drops it.
    assert "i-0edgerevorph" not in _detections(client)
    assert "i-0edgerevorph" not in _findings(client)
    assert "i-0edgerevorph" not in {
        r["resource_id"] for r in client.get("/resources").json()
    }


def test_edge_set_produces_two_findings(client):
    found = _findings(client)
    assert set(found) == {"i-0edgesched60", "i-0edgenocpu0"}
