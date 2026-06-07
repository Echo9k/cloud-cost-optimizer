"""FastAPI app — M0 walking skeleton.

Serves ONE hardcoded Finding over `GET /findings` and mounts the thin dashboard
as a static route (one process). No DB, no ingest, no detection logic yet —
those are M1+. The hardcoded Finding reflects the design thesis: an idle EC2
instance with a real proposed command, a confidence score, and a caveat.

Invariant: this app proposes commands; it never executes them and holds no
credential that can mutate anything.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import Finding

app = FastAPI(title="Cloud Cost Optimizer", version="0.1.0")

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"

# M0: a single hardcoded Finding (the idle instance from the fixture scenario).
_HARDCODED_FINDINGS: list[Finding] = [
    Finding(
        resource_id="i-0b2idle002",
        resource_type="ec2-instance",
        reason="Overall-mean CPU ~1.5-2% across the sample window — flat and idle.",
        confidence=0.9,
        caveat="Flat low utilization with no weekday/weekend structure; "
        "high confidence, but confirm no out-of-band use before decommissioning.",
        waste_estimate=30.00,
        proposed_command="aws ec2 terminate-instances --instance-ids i-0b2idle002",
        status="new",
    )
]


@app.get("/findings", response_model=list[Finding])
def get_findings() -> list[Finding]:
    """Return the current findings. M0: one hardcoded Finding."""
    return _HARDCODED_FINDINGS


@app.get("/")
def dashboard_index() -> FileResponse:
    """Serve the thin dashboard (pure API client, no cloud identity)."""
    return FileResponse(_DASHBOARD_DIR / "index.html")


# Static assets for the dashboard (thin client consumes the API only).
app.mount("/static", StaticFiles(directory=_DASHBOARD_DIR), name="static")
