"""M0 contract smoke test.

No fixture join yet (that is M1+). This asserts the walking-skeleton contract:
`GET /findings` returns 200 and exactly one well-formed `Finding` that honors
the two-axis + caveat invariant and the propose-never-execute boundary.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.models import Finding

client = TestClient(app)


def test_get_findings_returns_one_wellformed_finding():
    resp = client.get("/findings")
    assert resp.status_code == 200

    payload = resp.json()
    assert isinstance(payload, list)
    assert len(payload) == 1

    # Validates shape against the contract (raises if a field is missing/typed wrong).
    finding = Finding.model_validate(payload[0])

    # Two distinct axes, never collapsed.
    assert 0.0 <= finding.confidence <= 1.0
    assert finding.caveat, "every finding must carry a plain-language caveat"

    # Propose, never execute: command is a string, status starts at 'new'.
    assert isinstance(finding.proposed_command, str) and finding.proposed_command
    assert finding.status == "new"


def test_dashboard_index_served():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
