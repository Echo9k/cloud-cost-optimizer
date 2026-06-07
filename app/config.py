"""Detection configuration — single source of threshold truth.

All detector parameters live here so milestones thicken this module rather than
scattering magic numbers across the code.
"""

from __future__ import annotations

# --- M2: permanent-idle detector -------------------------------------------
# Overall-mean CPU (%) below this is treated as PERMANENTLY IDLE -> terminate
# candidate. A genuinely low idle cutoff, NOT an underutilization line: a
# weekday-busy / weekend-quiet resource has a high overall mean (~45% in the
# fixture) and must stay above this, because it is in use, not idle.
IDLE_MEAN_CPU_THRESHOLD = 15.0

# --- M3: weekday/weekend shape detector (scheduling candidate) -------------
# A SECOND detector alongside the M2 permanent-idle rule. It reuses
# IDLE_MEAN_CPU_THRESHOLD at DAILY grain: a day is "idle" if that day's mean CPU
# is below the threshold. idle_ratio = idle_days / total_days. A resource whose
# idle_ratio falls in [MIN, MAX] is busy most-but-not-all days -> looks like
# scheduled use (busy weekdays, quiet weekends), NOT permanently idle. This is a
# NON-termination finding. A permanently-idle resource (ratio ~1.0) and an active
# one (ratio ~0.0) both fall OUTSIDE this band, keeping the two detectors disjoint.
SCHEDULING_IDLE_RATIO_MIN = 0.15
SCHEDULING_IDLE_RATIO_MAX = 0.60

# --- M3: confidence tiers (defensible round numbers, not a false-precision curve)
CONFIDENCE_PERMANENTLY_IDLE = 0.9   # flat low all days -> safe to recommend terminate
CONFIDENCE_SCHEDULING_CANDIDATE = 0.4  # in use on a schedule -> lean back, do not kill
CONFIDENCE_ORPHAN = 0.3             # least signal = most deferential

# --- M3: waste projection ---------------------------------------------------
# The fixture spans 14 observed days. We project observed cost to a 30-day
# monthly run-rate: waste = (sum unblended_cost over window / observed_days) * 30.
# Waste is CLAIMED only for high-confidence findings (permanently-idle, orphan);
# the scheduling-candidate claims $0 -- we do not claim savings on something we
# are not recommending you delete.
WASTE_PROJECTION_DAYS = 30

