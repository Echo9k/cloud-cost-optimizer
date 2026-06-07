# Cloud Cost Optimizer — Project Constitution

## What this is
API-first FinOps tool. Ingests **two** exports — a cost export (CUR-shaped)
and a utilization export (CloudWatch-shaped) — joins them on resource ID,
flags idle / orphaned resources, and **proposes** decommission commands for
a human to run. It detects and recommends; it never executes.

Why two files: a billing row proves a resource *cost money*, not that it's
*idle* or *unused*. `lineItem/UsageAmount` is billed quantity (instance-hours),
identical whether CPU is at 2% or 90%. Utilization is the only signal that
separates idle from busy, so the metrics feed is mandatory, not optional.

## Hard invariants (never violate)
- Remediation commands are ALWAYS generated as proposals, NEVER executed.
  Never call destructive cloud APIs. The running app holds no credential
  that can mutate or delete anything. Ever.
- The human runs the command in their own terminal with their own
  credentials. That copy-paste step IS the confirmation layer — by design,
  not by limitation.
- Every Finding carries a `confidence` score AND a plain-language `caveat`.
  Never emit a binary "delete this" recommendation.
- Absence of a utilization signal is the MOST deferential case, not the most
  confident: an orphan (cost row, no metric row) is flagged high-cost /
  low-confidence with an explicit "orphan or data gap — verify" caveat.
- The human does not edit code. You (the agent) provide all logic and fixes.

## Stack
- Python 3.12, FastAPI, SQLite, Pydantic. `uv` for deps.
- Run: `uv run uvicorn app.main:app`. Test: `uv run pytest`.
- Dashboard is a thin client that consumes the API only. It holds NO cloud
  identity and never talks to AWS directly. Do not use Streamlit (it blurs
  the API-first boundary).

## Detection model (the two-output contract)
Every Finding exposes two distinct axes — do not collapse them into one number:
- `waste_estimate` ($) — magnitude. How much this resource costs. Only a
  positive waste *claim* for high-confidence findings; low-confidence
  findings show cost but claim $0 / unquantified waste.
- `confidence` (0–1) — recommendation safety, i.e. how sure we are that
  flagging it is correct. Surfaced as defensible round tiers (~0.9 flat-idle,
  ~0.4 periodic, ~0.3 orphan), not a false-precision continuous curve.

Mechanism: the **threshold** (overall-mean utilization) decides what to
*show*; the **weekday-vs-weekend** split decides how *hard to lean*. Finding
recurring weekday structure is itself the reason to back off — it triggers
the low-confidence caveat. These are two separate components.

## Contracts (don't reinvent these)
- `BillingLineItem`, `UtilizationSample`, and `Finding` schemas live in
  `app/models.py`. Treat them as fixed unless I explicitly change them.
- `Finding` fields: `resource_id`, `resource_type`, `reason`,
  `confidence: float`, `caveat: str`, `waste_estimate: float`,
  `proposed_command: str`, `status` (new / approved). Commands are proposals.
- Join key: `cur.lineItem/ResourceId` == `utilization.resource_id`.
  Resource IDs are normalized before joining (real CUR mixes ARNs and bare
  IDs; fixtures use the normalized form — this is a documented simplification).

## Working agreement
- TDD-by-fixture: every feature is verified against a file in `files/`
  (fixtures) with the expected output from `files/DATA_FORMAT.md` before we
  call it done. The fixture is the test, the spec, and the prompt.
- Commit at every milestone. Never leave the tree broken.
- I own milestone + acceptance criterion; plan mode proposes the tasks and I
  ratify them. I direct via spec, not by editing code.
- After every turn, append the prompt I gave you to `prompts.md`.
- Report 'Elapsed Time' at the end of every response (MVP goal 4–6h, max 16h).

## Scope boundaries (honor — these prevent drift)
- MVP runs entirely on synthetic fixtures. No live boto3 connection in the
  detection path. A real account is a teardown liability and the interesting
  scenarios (idle-but-periodic) only exist in crafted data anyway.
- In scope (MVP): idle detection from utilization shape; orphan detection via
  join-absence; confidence + caveat; proposed (never executed) commands.
- Out of scope (Phase 2, document don't build): ingesting a real account's
  exports; CUR 2.0 snake_case schema; human-armed deferred deletion
  (opt-in scheduling — never opt-out auto-terminate); ML-derived confidence.
