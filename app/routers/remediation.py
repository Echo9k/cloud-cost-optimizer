"""Remediation execution + audit endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import remediation as engine
from app.database import get_db
from app.models import Recommendation, RemediationAction
from app.schemas import RemediationOut, RemediationRequest

router = APIRouter(prefix="/api", tags=["remediation"])


@router.post(
    "/recommendations/{rec_id}/remediate", response_model=RemediationOut
)
def remediate_recommendation(
    rec_id: int,
    payload: RemediationRequest | None = None,
    db: Session = Depends(get_db),
) -> RemediationAction:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    dry_run = payload.dry_run if payload is not None else True
    try:
        return engine.remediate(db, rec, dry_run=dry_run)
    except engine.RemediationError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/remediations", response_model=list[RemediationOut])
def list_remediations(db: Session = Depends(get_db)) -> list[RemediationAction]:
    return (
        db.query(RemediationAction)
        .order_by(RemediationAction.executed_at.desc())
        .all()
    )
