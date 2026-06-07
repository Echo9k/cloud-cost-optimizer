"""Synthetic multi-cloud fleet for demos and tests.

Each entry is hand-tuned to trigger a specific rule so the dashboard shows a
representative spread of findings out of the box.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Recommendation, RemediationAction, Resource, ResourceState

FULL_TAGS = {"owner": "platform", "environment": "prod", "cost-center": "eng-100"}

SEED_RESOURCES: list[dict] = [
    # Idle compute — high CPU waste.
    dict(
        external_id="i-0a1b2c3d4e5f",
        name="legacy-batch-runner",
        provider="aws",
        region="us-east-1",
        service="ec2",
        resource_type="m5.2xlarge",
        state=ResourceState.RUNNING,
        monthly_cost=276.48,
        cpu_utilization=1.8,
        tags=FULL_TAGS,
        age_days=210,
    ),
    # Rightsize candidate — moderate-low CPU.
    dict(
        external_id="i-9z8y7x6w5v",
        name="api-staging",
        provider="aws",
        region="us-east-1",
        service="ec2",
        resource_type="c5.xlarge",
        state=ResourceState.RUNNING,
        monthly_cost=124.10,
        cpu_utilization=22.0,
        tags=FULL_TAGS,
        age_days=95,
    ),
    # Orphaned EBS volume.
    dict(
        external_id="vol-0f1e2d3c4b",
        name="detached-data-vol",
        provider="aws",
        region="us-west-2",
        service="ebs",
        resource_type="gp3-500gb",
        state=ResourceState.UNATTACHED,
        monthly_cost=40.00,
        cpu_utilization=0.0,
        tags=FULL_TAGS,
        age_days=140,
    ),
    # Stale stopped VM (also missing tags -> two findings).
    dict(
        external_id="vm-azure-00123",
        name="old-jenkins-agent",
        provider="azure",
        region="eastus",
        service="vm",
        resource_type="Standard_D4s_v3",
        state=ResourceState.STOPPED,
        monthly_cost=180.00,
        cpu_utilization=0.0,
        tags={"owner": "ci"},
        age_days=64,
    ),
    # Healthy, well-tagged, busy resource — should produce NO findings.
    dict(
        external_id="i-healthyprod01",
        name="checkout-service",
        provider="aws",
        region="us-east-1",
        service="ec2",
        resource_type="m5.large",
        state=ResourceState.RUNNING,
        monthly_cost=69.12,
        cpu_utilization=68.0,
        tags=FULL_TAGS,
        age_days=300,
    ),
    # GCP idle compute, missing required tags.
    dict(
        external_id="gce-data-pipe-7",
        name="data-pipeline-worker",
        provider="gcp",
        region="us-central1",
        service="gce",
        resource_type="n2-standard-8",
        state=ResourceState.RUNNING,
        monthly_cost=389.50,
        cpu_utilization=3.2,
        tags={"environment": "dev"},
        age_days=45,
    ),
    # Orphaned static IP, untagged.
    dict(
        external_id="eip-55ff00aa",
        name="dangling-elastic-ip",
        provider="aws",
        region="eu-west-1",
        service="eip",
        resource_type="static-ipv4",
        state=ResourceState.UNATTACHED,
        monthly_cost=3.60,
        cpu_utilization=0.0,
        tags={},
        age_days=88,
    ),
]


def seed(db: Session, reset: bool = True) -> int:
    """Populate the database with the synthetic fleet.

    When ``reset`` is true, wipes existing rows first so seeding is repeatable.
    Returns the number of resources inserted.
    """
    if reset:
        db.query(RemediationAction).delete()
        db.query(Recommendation).delete()
        db.query(Resource).delete()
        db.commit()

    for row in SEED_RESOURCES:
        db.add(Resource(**row))
    db.commit()
    return len(SEED_RESOURCES)
