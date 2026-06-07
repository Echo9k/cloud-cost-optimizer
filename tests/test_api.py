"""End-to-end API tests covering the full optimize → remediate workflow."""

from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dashboard_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Cloud Cost Optimizer" in r.text


def test_seed_and_list(client):
    r = client.post("/api/resources/seed")
    assert r.status_code == 201
    count = r.json()["seeded_resources"]
    assert count > 0
    listed = client.get("/api/resources").json()
    assert len(listed) == count


def test_create_resource_and_conflict(client):
    payload = {
        "external_id": "i-unique",
        "name": "test",
        "provider": "aws",
        "region": "us-east-1",
        "service": "ec2",
        "resource_type": "m5.large",
        "monthly_cost": 50.0,
        "cpu_utilization": 1.0,
        "tags": {},
    }
    assert client.post("/api/resources", json=payload).status_code == 201
    assert client.post("/api/resources", json=payload).status_code == 409


def test_scan_generates_recommendations(client):
    client.post("/api/resources/seed")
    scan = client.post("/api/optimizer/scan").json()
    assert scan["recommendations_created"] > 0
    assert scan["potential_monthly_savings"] > 0
    recs = client.get("/api/recommendations?status=open").json()
    assert len(recs) == scan["recommendations_created"]


def test_scan_is_idempotent(client):
    client.post("/api/resources/seed")
    first = client.post("/api/optimizer/scan").json()
    second = client.post("/api/optimizer/scan").json()
    assert first["recommendations_created"] == second["recommendations_created"]


def test_dry_run_changes_nothing(client):
    client.post("/api/resources/seed")
    client.post("/api/optimizer/scan")
    rec = client.get("/api/recommendations?status=open").json()[0]
    res = client.post(
        f"/api/recommendations/{rec['id']}/remediate", json={"dry_run": True}
    ).json()
    assert res["status"] == "simulated"
    assert res["realized_savings"] == 0.0
    # Recommendation stays open after a dry run.
    still = client.get(f"/api/recommendations/{rec['id']}").json()
    assert still["status"] == "open"


def test_apply_remediation_books_savings(client):
    client.post("/api/resources/seed")
    client.post("/api/optimizer/scan")
    rec = client.get("/api/recommendations?status=open").json()[0]
    res = client.post(
        f"/api/recommendations/{rec['id']}/remediate", json={"dry_run": False}
    ).json()
    assert res["status"] == "applied"
    assert res["realized_savings"] == rec["estimated_monthly_savings"]
    applied = client.get(f"/api/recommendations/{rec['id']}").json()
    assert applied["status"] == "applied"

    summary = client.get("/api/summary").json()
    assert summary["realized_monthly_savings"] >= res["realized_savings"]


def test_cannot_remediate_twice(client):
    client.post("/api/resources/seed")
    client.post("/api/optimizer/scan")
    rec = client.get("/api/recommendations?status=open").json()[0]
    client.post(
        f"/api/recommendations/{rec['id']}/remediate", json={"dry_run": False}
    )
    conflict = client.post(
        f"/api/recommendations/{rec['id']}/remediate", json={"dry_run": False}
    )
    assert conflict.status_code == 409


def test_dismiss(client):
    client.post("/api/resources/seed")
    client.post("/api/optimizer/scan")
    rec = client.get("/api/recommendations?status=open").json()[0]
    assert (
        client.post(f"/api/recommendations/{rec['id']}/dismiss").status_code == 200
    )
    dismissed = client.get(f"/api/recommendations/{rec['id']}").json()
    assert dismissed["status"] == "dismissed"
