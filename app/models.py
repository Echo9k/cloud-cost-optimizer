"""ORM models for resources, recommendations, and remediation actions."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResourceState(str, enum.Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    UNATTACHED = "unattached"
    TERMINATED = "terminated"


class RecommendationType(str, enum.Enum):
    IDLE = "idle"
    RIGHTSIZE = "rightsize"
    ORPHANED = "orphaned"
    UNTAGGED = "untagged"
    STALE = "stale"


class Severity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationStatus(str, enum.Enum):
    OPEN = "open"
    APPLIED = "applied"
    DISMISSED = "dismissed"


class RemediationStatus(str, enum.Enum):
    SIMULATED = "simulated"  # dry-run executed, nothing changed
    APPLIED = "applied"  # change committed to the (simulated) cloud
    FAILED = "failed"


class Resource(Base):
    """A cloud resource ingested from a billing/inventory feed."""

    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    provider: Mapped[str] = mapped_column(String(32))  # aws | gcp | azure
    region: Mapped[str] = mapped_column(String(64))
    service: Mapped[str] = mapped_column(String(64))  # ec2 | rds | ebs | ...
    resource_type: Mapped[str] = mapped_column(String(64))  # e.g. m5.xlarge
    state: Mapped[ResourceState] = mapped_column(
        Enum(ResourceState), default=ResourceState.RUNNING
    )
    monthly_cost: Mapped[float] = mapped_column(Float, default=0.0)
    cpu_utilization: Mapped[float] = mapped_column(Float, default=0.0)  # avg %
    tags: Mapped[dict] = mapped_column(JSON, default=dict)
    age_days: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class Recommendation(Base):
    """An optimization opportunity emitted by the rules engine."""

    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id"), index=True
    )
    rec_type: Mapped[RecommendationType] = mapped_column(Enum(RecommendationType))
    severity: Mapped[Severity] = mapped_column(Enum(Severity))
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(RecommendationStatus), default=RecommendationStatus.OPEN
    )
    estimated_monthly_savings: Mapped[float] = mapped_column(Float, default=0.0)
    suggested_action: Mapped[str] = mapped_column(String(64))  # stop | downsize ...
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    resource: Mapped["Resource"] = relationship(back_populates="recommendations")
    remediations: Mapped[list["RemediationAction"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )


class RemediationAction(Base):
    """An audit record for every remediation attempt (dry-run or applied)."""

    __tablename__ = "remediation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(64))
    dry_run: Mapped[bool] = mapped_column(default=True)
    status: Mapped[RemediationStatus] = mapped_column(Enum(RemediationStatus))
    realized_savings: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[str] = mapped_column(Text, default="")
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    recommendation: Mapped["Recommendation"] = relationship(
        back_populates="remediations"
    )
