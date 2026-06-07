"""Unit tests for the rules engine — each rule in isolation."""

from __future__ import annotations

from app import optimizer
from app.models import RecommendationType, Resource, ResourceState

FULL_TAGS = {"owner": "a", "environment": "prod", "cost-center": "c1"}


def _resource(**overrides) -> Resource:
    base = dict(
        external_id="x",
        name="n",
        provider="aws",
        region="us-east-1",
        service="ec2",
        resource_type="m5.large",
        state=ResourceState.RUNNING,
        monthly_cost=100.0,
        cpu_utilization=50.0,
        tags=FULL_TAGS,
        age_days=10,
    )
    base.update(overrides)
    return Resource(**base)


def _types(resource: Resource) -> set[RecommendationType]:
    return {hit.rec_type for hit in optimizer.evaluate(resource)}


def test_idle_compute_flagged():
    r = _resource(cpu_utilization=2.0)
    hits = optimizer.evaluate(r)
    assert RecommendationType.IDLE in _types(r)
    assert hits[0].estimated_monthly_savings == 100.0  # full cost reclaimed


def test_rightsize_band():
    r = _resource(cpu_utilization=25.0)
    types = _types(r)
    assert RecommendationType.RIGHTSIZE in types
    assert RecommendationType.IDLE not in types  # bands are disjoint


def test_healthy_resource_no_findings():
    assert _types(_resource(cpu_utilization=70.0)) == set()


def test_orphaned_flagged():
    r = _resource(state=ResourceState.UNATTACHED, service="ebs", cpu_utilization=0.0)
    assert RecommendationType.ORPHANED in _types(r)


def test_stale_stopped_flagged():
    r = _resource(state=ResourceState.STOPPED, age_days=90, cpu_utilization=0.0)
    assert RecommendationType.STALE in _types(r)


def test_fresh_stopped_not_stale():
    r = _resource(state=ResourceState.STOPPED, age_days=3, cpu_utilization=0.0)
    assert RecommendationType.STALE not in _types(r)


def test_untagged_flagged():
    r = _resource(tags={"owner": "a"}, cpu_utilization=70.0)
    types = _types(r)
    assert RecommendationType.UNTAGGED in types


def test_idle_and_untagged_compound():
    r = _resource(cpu_utilization=1.0, tags={})
    types = _types(r)
    assert {RecommendationType.IDLE, RecommendationType.UNTAGGED} <= types
