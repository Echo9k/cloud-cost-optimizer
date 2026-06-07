# Cloud Cost Optimizer & Remediation Engine: Milestones

Milestones are **vertical slices**: walking skeleton first, then thicken —
never horizontal layers. Each is a committed, rollback-safe, demoable state.
Each acceptance criterion is written as **fixture + expected output**, which
doubles as the prompt. "Maps to brief" ties each slice back to the task's
value chain.

The cut line (declared up front, cut from the bottom under time pressure,
never the middle): **floor = M0–M2 + a thin M3 (real confidence scores at
minimum) + M4 + minimal M5.** Tradeable under pressure = M3 periodicity
depth, M5 polish, M6 edge fixtures.

---

## Milestone table

| # | Milestone | Maps to brief | Acceptance criterion |
|---|-----------|---------------|----------------------|
| **M0** | Walking skeleton + contracts | (wrapper) | `GET /findings` returns one hardcoded `Finding`; dashboard renders it; `BillingLineItem`, `UtilizationSample`, `Finding` defined in `app/models.py`; repo init + committed. |
| **M1** | Ingest + join | "ingests billing exports" | POST `cur_sample.csv` + `utilization_sample.csv` → DB holds both → `GET /resources` returns each resource with its cost rows and (if present) its utilization series joined on resource ID. The orphan volume appears with cost rows and **no** metric series. |
| **M2** | Detection, baseline rule | "identify idle/orphaned" | Threshold on overall-mean utilization flags the idle instance and not the active one (binary, no confidence yet). Orphan (no metric row) is flagged via join-absence. |
| **M3** | Confidence + false-positive guard *(over-invest here)* | "identify", done well | Against the 4-resource fixture: idle → high confidence (~0.9); periodic → **low** confidence (~0.4) + caveat; active → no finding; orphan → high-cost / low confidence (~0.3) + "orphan or data gap" caveat. |
| **M4** | Remediation generation | "generate CLI/API logic" | Each flagged finding emits the correct decommission command string (e.g. `aws ec2 terminate-instances --instance-ids …`, `aws ec2 delete-volume --volume-id …`). Nothing executes. "Approve" only flips `status`. Commands carry the finding's confidence + caveat. |
| **M5** | Dashboard / value surface | "dashboard" | Dashboard shows total claimed $ waste + per-finding confidence / caveat / command / approve, all sourced from the API. Sorted by waste, colored by confidence. The periodic instance sits high on cost but flagged low-confidence — the demo image. |
| **M6** | Harden + deck + decommission | (wrapper + deliverables) | Edge fixtures pass; deck generated; README runs from zero; any live test resources/accounts closed and confirmed. |

---

## Detection model carried into M2–M5 (the contract)

Two outputs per finding, never collapsed into one:
- `waste_estimate` ($) — magnitude. A positive waste **claim** only for
  high-confidence findings; low-confidence findings show cost but claim
  $0 / unquantified.
- `confidence` (0–1) — recommendation safety, surfaced as defensible round
  tiers, not a continuous curve.

Two-stage logic:
1. **Threshold** (overall-mean utilization) decides *what to show*. Flag broad
   — catch everything low.
2. **Weekday-vs-weekend split** decides *how hard to lean*. A large weekday/
   weekend gap = scheduled-use signal = confidence collapses, regardless of
   mean. Finding structure is the reason to back off.

Periodicity is **pattern-flagged**, not a computed gradient: "weekday mean
materially exceeds weekend mean → looks scheduled → low confidence + caveat."
With 14 days / 4 resources a gradient is false precision; the rule is the
honest, demoable version. Gradient is a Phase-2 "with more history" line.

---

## M3 worked decomposition

- **M3.1 — Confidence scaffold** (model + plumbing): replace the binary flag
  with `confidence: float` + `reason: str` + `waste_estimate: float` on every
  Finding.
- **M3.2 — Utilization-shape analysis** (the real judgment):
  - Use the existing `utilization_sample.csv` as the spec (fixture first).
  - Compute per-resource: overall mean, weekday mean, weekend mean.
  - Map shape → confidence tier: flat-and-low → ~0.9; low-mean-but-weekday-
    heavy → ~0.4; orphan/no-signal → ~0.3; active → no finding.
  - Acceptance test against the 4-resource fixture.
- **M3.3 — Caveat generation** (the human-in-the-loop output): attach plain-
  language caveats to low-confidence findings — periodic: "low average usage
  but regular weekday spikes; verify before decommissioning"; orphan:
  "billing with no utilization signal — orphan or data gap, confirm before
  acting."

**Through-line:** the first task in every detection milestone is *confirm the
fixture + expected output*. The fixture is simultaneously the test, the spec,
and the prompt.

---

## Granularity decision (daily fixtures, weekday/weekend framing)

The fixtures' `utilization_sample.csv` is **daily** (`period_seconds = 86400`).
The M3 method is a **weekday-mean vs weekend-mean** day-of-week split, which
needs day resolution — daily is the right fit, not a compromise. Hourly would
add 24× the rows (unused resolution) and tempt over-engineering
(autocorrelation/FFT) we already rejected. Daily keeps the fixture small
enough for the agent to reason about the whole file correctly — which directly
attacks the no-manual-edits hallucination risk.

- **Headline scenario is framed as "busy weekdays, quiet weekends,"** NOT an
  intraday Monday-9am spike.
- Thin-sample honesty: 14 days ≈ 10 weekday + 4 weekend samples. State the
  Phase-2 line out loud — "more history sharpens the gap."
- **M3.3 implementation note:** derive day-of-week from the `timestamp`
  column, do not hardcode row indices. Fixture starts Mon 2026-05-18, so
  weekends are 05-23/24 and 05-30/31. The acceptance test must assert against
  those dates, not positional rows, so fixture re-ordering can't silently
  break it.

---

## IAM / identity picture (M6 live-capstone reference, deck slide)

The running system's maximum capability is to **read a billing file**.
- **Setup role** (create/destroy) — used by you + the agent during setup only,
  never by the running system; deleted at teardown.
- **Detection role** (read-only billing) — the *only* credential the running
  app holds. Cannot mutate anything.
- **Remediation** — *no identity*. Commands are strings; the human's own
  terminal supplies the credentials. The airgap.
- **Dashboard** — *no cloud identity*. Pure client of our API.

---

## Deck hooks (captured as they fell out of design)

1. **Human-in-the-loop architecture** — chose the one project where the right
   architecture *is* the stated cultural value; the engine recommends, never
   executes; the IAM diagram is that thesis made physical.
2. **Two-feed insight** — identical cost rows beside divergent utilization:
   "this is why a cost report alone can't find waste." (Opening image.)
3. **Spend-vs-state solved in MVP** — orphan detection falls out of the join
   (state inferred from absence), no live cloud call needed.
4. **Threshold vs confidence** — "the threshold decides what to show you; the
   confidence decides how hard I lean. Different jobs."
5. **Honest dollar number** — "I claim $X of waste, and I'm specifically not
   counting the ambiguous one. The number is honest to the dollar."
6. **Structure-hunting detector** — "my detector hunts for structure; finding
   structure is a reason to back off, not push forward." The orphan (least
   signal) gets the most deferential treatment.
7. **Architect, not micromanager** — owned milestones / acceptance criteria;
   let plan mode propose tasks and reviewed them.
8. **Tooling restraint** — one connector (context7), chosen against the
   primary risk (hallucinated cloud-API syntax under no-manual-edits).
