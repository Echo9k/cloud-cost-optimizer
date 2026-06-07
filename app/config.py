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
# PLACEHOLDER — not used yet. M3 will add a SEPARATE shape-based detector that
# flags periodic / scheduled-use resources (busy weekdays, quiet weekends) as
# NON-termination scheduling candidates. Its parameters (e.g. weekday-vs-weekend
# gap threshold, confidence tiers) will be defined here so M3 thickens this
# module instead of refactoring it. Do not implement here.
