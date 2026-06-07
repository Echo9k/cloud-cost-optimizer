"""Optimizer scan + recommendation lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import optimizer
from app.database import get_db
from app.models import (
    Recommendation,
    RecommendationStatus,
    RecommendationType,
    Severity,
)
from app.schemas import RecommendationOut, ScanResult

router = APIRouter(prefix="/api", tags=["recommendations"])


@router.post("/optimizer/scan", response_model=ScanResult)
def run_scan(db: Session = Depends(get_db)) -> ScanResult:
    """Run the rules engine across the fleet and refresh open recommendations."""
    scanned, created, potential = optimizer.scan(db)
    return ScanResult(
        scanned_resources=scanned,
        recommendations_created=created,
        potential_monthly_savings=potential,
    )


@router.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    db: Session = Depends(get_db),
    status: RecommendationStatus | None = Query(default=None),
    severity: Severity | None = Query(default=None),
    rec_type: RecommendationType | None = Query(default=None),
) -> list[Recommendation]:
    query = db.query(Recommendation)
    if status is not None:
        query = query.filter(Recommendation.status == status)
    if severity is not None:
        query = query.filter(Recommendation.severity == severity)
    if rec_type is not None:
        query = query.filter(Recommendation.rec_type == rec_type)
    return query.order_by(
        Recommendation.estimated_monthly_savings.desc()
    ).all()


@router.get("/recommendations/{rec_id}", response_model=RecommendationOut)
def get_recommendation(
    rec_id: int, db: Session = Depends(get_db)
) -> Recommendation:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/recommendations/{rec_id}/dismiss", response_model=RecommendationOut)
def dismiss_recommendation(
    rec_id: int, db: Session = Depends(get_db)
) -> Recommendation:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    if rec.status != RecommendationStatus.OPEN:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot dismiss a '{rec.status.value}' recommendation.",
        )
    rec.status = RecommendationStatus.DISMISSED
    db.commit()
    db.refresh(rec)
    return rec
