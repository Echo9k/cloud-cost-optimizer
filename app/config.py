"""Tunable thresholds for the optimization rules engine.

Centralizing these makes every rule testable and lets operators adjust the
aggressiveness of recommendations without touching engine logic.
"""

from __future__ import annotations

import os


class Settings:
    # Database -------------------------------------------------------------
    DATABASE_URL: str = os.getenv("CCO_DATABASE_URL", "sqlite:///./cco.db")

    # Idle detection: a compute resource averaging below this CPU % over the
    # lookback window is considered idle and a candidate for termination.
    IDLE_CPU_PCT: float = float(os.getenv("CCO_IDLE_CPU_PCT", "5.0"))

    # Rightsizing: utilization is non-trivial but low enough that the resource
    # can move down a size tier. Applies between IDLE_CPU_PCT and this value.
    RIGHTSIZE_CPU_PCT: float = float(os.getenv("CCO_RIGHTSIZE_CPU_PCT", "40.0"))

    # Fraction of monthly cost recovered by downsizing one tier.
    RIGHTSIZE_SAVINGS_FRACTION: float = float(
        os.getenv("CCO_RIGHTSIZE_SAVINGS_FRACTION", "0.5")
    )

    # Age (days) past which an unattached/stale resource is flagged.
    STALE_AGE_DAYS: int = int(os.getenv("CCO_STALE_AGE_DAYS", "30"))

    # Tags every governed resource is expected to carry.
    REQUIRED_TAGS: tuple[str, ...] = tuple(
        os.getenv("CCO_REQUIRED_TAGS", "owner,environment,cost-center").split(",")
    )


settings = Settings()
