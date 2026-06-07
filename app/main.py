"""FastAPI app — API-first cost optimizer.

Mounts the thin dashboard as a static route (one process) and exposes the
detection pipeline: POST /ingest, GET /resources (raw join), GET /detections
(binary signals), GET /findings (real findings, M0 contract shape).

Invariant: this app proposes commands; it never executes them and holds no
credential that can mutate anything.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.approvals import FindingNotApprovable, FindingNotFound, approve
from app.db import get_session, init_db
from app.detect import DetectionSignal, detect
from app.findings import build_findings
from app.ingest import ingest_feeds
from app.models import Finding
from app.resources import ResourceView, get_resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Cloud Cost Optimizer", version="0.1.0", lifespan=lifespan)

_DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


@app.get("/findings", response_model=list[Finding])
def get_findings(session: Session = Depends(get_session)) -> list[Finding]:
    """Real findings derived from the joined data, with approval state overlaid."""
    return build_findings(session)


@app.post("/findings/{resource_id}/approve", response_model=Finding)
def approve_finding(
    resource_id: str, session: Session = Depends(get_session)
) -> Finding:
    """Flip a finding's status new -> approved and PERSIST it. Executes nothing.

    Writes a single row to the approvals table; the proposed_command is surfaced
    as text for the human to run in their own terminal.
    """
    try:
        return approve(session, resource_id)
    except FindingNotFound:
        raise HTTPException(
            status_code=404, detail=f"No current finding for resource '{resource_id}'."
        )
    except FindingNotApprovable:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Finding for '{resource_id}' is a scheduling candidate "
                "(non-termination) and is not approvable."
            ),
        )


@app.post("/ingest")
def ingest(
    cur_file: UploadFile = File(..., description="cur_sample.csv (cost export)"),
    utilization_file: UploadFile = File(..., description="utilization_sample.csv"),
    session: Session = Depends(get_session),
) -> dict[str, int]:
    """Ingest BOTH feeds in one call; persist to two separate tables."""
    return ingest_feeds(session, cur_file.file.read(), utilization_file.file.read())


@app.get("/resources", response_model=list[ResourceView])
def resources(session: Session = Depends(get_session)) -> list[ResourceView]:
    """Billing-primary LEFT join of cost rows + utilization series. Raw, no detection."""
    return get_resources(session)


@app.get("/detections", response_model=list[DetectionSignal])
def detections(session: Session = Depends(get_session)) -> list[DetectionSignal]:
    """M2 baseline permanent-idle detection. Binary signals, not Findings."""
    return detect(session)


@app.get("/")
def dashboard_index() -> FileResponse:
    """Serve the thin dashboard (pure API client, no cloud identity)."""
    return FileResponse(_DASHBOARD_DIR / "index.html")


# Static assets for the dashboard (thin client consumes the API only).
app.mount("/static", StaticFiles(directory=_DASHBOARD_DIR), name="static")
