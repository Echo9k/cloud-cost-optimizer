Lead Architect mode: ON.

We are building a Python-based, API-first **Cloud Cost Optimizer & Remediation Engine**
using a free database and a dashboard.

**Rules:**
● No Manual Edits: You provide all logic and fixes. I will not edit any code.
● Audit Log: You must maintain a file named prompts.md. After every turn, update that file (or
provide the text block) with the prompt I just used.
● Time-Check: Start a timer. Goal is an MVP in 4-6 hours (Max window: 16h). Report 'Elapsed
Time' at the end of every response. Acknowledge and let's start.

---

## M0 — planning prompt

STOP-AND-PLAN PROTOCOL — build ONE milestone at a time; no code until the plan is
ratified. Start at M0 and ONLY M0; do not read ahead and sprint to a finished app.
Read source-of-truth files (CLAUDE.md, MILESTONES.md, files/DATA_FORMAT.md + fixtures).
Confirm the three invariants (propose-never-execute; confidence + caveat via two-feed
join; orphan/absence is most deferential). FIRST reply: (a) rules ack, (b) three
invariants, (c) plan-mode task breakdown for M0 ONLY — app/models.py schemas, GET
/findings returning one hardcoded Finding, thin dashboard consuming the API, repo init
+ first commit. No code, no scaffolding beyond M0. Wait for explicit "ratified — build it".

## M0 — build prompt

Build it. Two clarifications: (1) Dashboard = FastAPI static route, one process.
(2) Contract location: Pydantic in app/models.py is correct; anticipate M1 — keep
Pydantic API-contract models separate from SQLite/SQLAlchemy ORM persistence models,
do not combine API schema with an ORM row; note the intent now, don't build it yet.
Build M0 (T1–T6) as planned. Commit at end. Report Elapsed Time and GET /findings
sample payload.
## M1 — planning prompt

M0 accepted. GET /findings payload is the contract — do not change it this
milestone. At end of each ratified milestone, commit + push to origin on the
build branch, report SHA, do not push to main, ask first. Move to M1 (ingest +
join) and ONLY M1; plan first, no code until "ratified — build it". RESEARCH
FIRST: re-read app/models.py, files/DATA_FORMAT.md, both CSV headers; state the
join key on each side and the orphan row. M1 acceptance: POST cur+utilization →
DB holds BOTH feeds → GET /resources returns each resource with cost rows and
(if present) joined utilization series; orphan volume appears with cost rows and
NO metric series. Constraints: (1) two feeds = two tables, don't collapse util
into a billing column; (2) LEFT join, billing-primary on resource_id, every
billed resource appears, state what the orphan looks like post-join; (3) orphan
survives the join, not dropped, not flagged yet; (4) SQLAlchemy ORM separate
from Pydantic contracts; (5) name resource-id normalization as join-prep. OUT
of scope: any detection/threshold/classification/confidence/weekday logic; GET
/resources returns RAW joined data; do NOT modify hardcoded GET /findings.

## M1 — build prompt

ratified — build it

## M2 — planning prompt (corrected design)

M1 accepted. Push build branch freely; ask only before main/PR. Move to M2
(detection, baseline idle rule), plan first, no code until ratified. RESEARCH:
re-read app/resources.py + DATA_FORMAT.md; open utilization_sample.csv; state
rough mean CPU for active/idle/periodic. M2 acceptance: threshold rule flags
idle, not active; orphan via absence; binary only. CORRECTED DESIGN: M2 detects
PERMANENTLY IDLE only (flat-low all days -> terminate). PERIODIC/scheduled-use
is IN USE, NOT a termination candidate -> deferred to M3 as a separate shape
detector, not by widening M2's threshold. Threshold stays genuinely low (~15%),
a defensible idle cutoff, NOT 50%. At 15%: idle flagged, active not, periodic
NOT flagged (intended, not a miss). Constraints: (C1) util series only, never
cost; (C2) binary DetectionSignal, not a Finding; (C3) orphan = empty series,
own branch, flagged via absence, basis="orphan-no-metrics", mean=None. config.py
single threshold source, structured so M3 adds weekday/weekend params cleanly
(don't build them now). GET /detections new; GET /findings frozen at M0 payload.
Tests assert periodic NOT flagged with comment that M3 adds the scheduling path.

## M2 — build prompt

ratified — build it
