"""Pydantic schemas — the external API contract."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    RecommendationStatus,
    RecommendationType,
    RemediationStatus,
    ResourceState,
    Severity,
)


# --- Resources -----------------------------------------------------------
class ResourceCreate(BaseModel):
    external_id: str
    name: str
    provider: str = Field(examples=["aws", "gcp", "azure"])
    region: str
    service: str = Field(examples=["ec2", "rds", "ebs"])
    resource_type: str = Field(examples=["m5.xlarge"])
    state: ResourceState = ResourceState.RUNNING
    monthly_cost: float = 0.0
    cpu_utilization: float = 0.0
    tags: dict[str, str] = Field(default_factory=dict)
    age_days: int = 0


class ResourceOut(ResourceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# --- Recommendations -----------------------------------------------------
class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resource_id: int
    rec_type: RecommendationType
    severity: Severity
    status: RecommendationStatus
    estimated_monthly_savings: float
    suggested_action: str
    rationale: str
    created_at: datetime


# --- Remediation ---------------------------------------------------------
class RemediationRequest(BaseModel):
    dry_run: bool = Field(
        default=True,
        description="When true (default) nothing is changed; the action is "
        "simulated and audited.",
    )


class RemediationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    recommendation_id: int
    action_type: str
    dry_run: bool
    status: RemediationStatus
    realized_savings: float
    detail: str
    executed_at: datetime


# --- Aggregates ----------------------------------------------------------
class ScanResult(BaseModel):
    scanned_resources: int
    recommendations_created: int
    potential_monthly_savings: float


class Summary(BaseModel):
    total_resources: int
    total_monthly_cost: float
    open_recommendations: int
    potential_monthly_savings: float
    realized_monthly_savings: float
    savings_by_type: dict[str, float]
    counts_by_severity: dict[str, int]
