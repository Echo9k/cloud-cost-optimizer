"""Aggregate KPIs powering the dashboard header."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Recommendation,
    RecommendationStatus,
    RemediationAction,
    RemediationStatus,
    Resource,
)
from app.schemas import Summary

router = APIRouter(prefix="/api", tags=["summary"])


@router.get("/summary", response_model=Summary)
def get_summary(db: Session = Depends(get_db)) -> Summary:
    resources = db.query(Resource).all()
    total_cost = sum(r.monthly_cost for r in resources)

    open_recs = (
        db.query(Recommendation)
        .filter(Recommendation.status == RecommendationStatus.OPEN)
        .all()
    )

    savings_by_type: dict[str, float] = defaultdict(float)
    counts_by_severity: dict[str, int] = defaultdict(int)
    potential = 0.0
    for rec in open_recs:
        savings_by_type[rec.rec_type.value] += rec.estimated_monthly_savings
        counts_by_severity[rec.severity.value] += 1
        potential += rec.estimated_monthly_savings

    realized = (
        db.query(RemediationAction)
        .filter(RemediationAction.status == RemediationStatus.APPLIED)
        .all()
    )
    realized_savings = sum(r.realized_savings for r in realized)

    return Summary(
        total_resources=len(resources),
        total_monthly_cost=round(total_cost, 2),
        open_recommendations=len(open_recs),
        potential_monthly_savings=round(potential, 2),
        realized_monthly_savings=round(realized_savings, 2),
        savings_by_type={k: round(v, 2) for k, v in savings_by_type.items()},
        counts_by_severity=dict(counts_by_severity),
    )
